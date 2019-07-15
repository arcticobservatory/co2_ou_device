import machine
import pycom
import time

import logging
_logger = logging.getLogger("co2unit_main")

import co2unit_hw
import pycom_util

# Normal operation
STATE_UNKNOWN           = const(0)
STATE_QUICK_HW_TEST     = const(1)
STATE_LTE_TEST          = const(2)
STATE_UPDATE            = const(3)
STATE_SCHEDULE          = const(4)
STATE_TAKE_MEASUREMENT  = const(5)
STATE_COMMUNICATE       = const(6)

MEASURE_FREQ_MINUTES = 5
COMM_SCHEDULE_HOUR = None
COMM_SCHEDULE_MINUTE = 7

next_state_on_boot = pycom_util.mk_on_boot_fn("co2_wake_next")

def determine_state_after_reset():
    # Specific reset causes:
    # PWRON_RESET: fresh power on, reset button
    # DEEPSLEEP_RESET: waking from deep sleep
    # WDT_RESET: watchdog timer or machine.reset() in script
    # SOFT_RESET: ctrl+D in REPL
    #
    # Undocumented:
    # SW_CPU_RESET (0xc): core dump crash
    reset_cause = machine.reset_cause()

    if reset_cause == machine.PWRON_RESET:
        _logger.info("Power-on reset")
        _logger.info("Do self test")
        return STATE_QUICK_HW_TEST

    if reset_cause in [machine.SOFT_RESET, machine.WDT_RESET, machine.DEEPSLEEP_RESET]:
        if reset_cause in [machine.SOFT_RESET, machine.WDT_RESET]:
            _logger.info("Soft reset or self-reset")
        elif reset_cause == machine.DEEPSLEEP_RESET:
            _logger.info("Woke up from deep sleep")

        _logger.info("Checking scheduled action...")
        scheduled = next_state_on_boot(default=STATE_UNKNOWN)
        if scheduled == STATE_UNKNOWN:
            _logger.warning("Woke from deep sleep, but no activity scheduled. Possible crash.")
        return scheduled

    _logger.warning("Unknown wake circumstances")
    return STATE_UNKNOWN

def schedule_wake():
    import timeutil

    measure_time = timeutil.next_even_minutes(MEASURE_FREQ_MINUTES)
    seconds_until_measure = timeutil.seconds_until_time(measure_time)

    comm_time = timeutil.next_even_minutes(10, plus=COMM_SCHEDULE_MINUTE)
    seconds_until_comm = timeutil.seconds_until_time(comm_time)

    _logger.info("Next measurement  at %s (T minus %d seconds)", measure_time, seconds_until_measure)
    _logger.info("Next comm         at %s (T minus %d seconds)", comm_time, seconds_until_comm)

    if seconds_until_comm < seconds_until_measure:
        _logger.info("Comm next")
        next_state_on_boot(STATE_COMMUNICATE)
        return seconds_until_comm * 1000

    else:
        _logger.info("Measurement next")
        next_state_on_boot(STATE_TAKE_MEASUREMENT)
        return seconds_until_measure * 1000

def run(hw, next_state, hw_test_only=False):

    # Clear wake hints so we can detect a crash
    next_state_on_boot(erase=True)

    if next_state == STATE_UNKNOWN:
        _logger.warning("Unknown start state. Default to scheduling sleep.")
        next_state = STATE_SCHEDULE

    # Run chosen state
    # --------------------------------------------------

    # Turn on peripherals
    hw.power_peripherals(True)

    if next_state in [STATE_QUICK_HW_TEST, STATE_LTE_TEST]:
        # Reset heartbeat to initialize RGB LED, for test feedback
        pycom.heartbeat(True)
        pycom.heartbeat(False)

        # Do self-test
        import co2unit_self_test

        if next_state == STATE_QUICK_HW_TEST:
            _logger.info("Starting quick self test...")
            co2unit_self_test.quick_test_hw(hw)
            next_state_on_boot(STATE_UPDATE)

        elif next_state == STATE_LTE_TEST:

            _logger.info("Starting LTE test...")
            co2unit_self_test.test_lte_ntp(hw)
            next_state_on_boot(STATE_SCHEDULE)

        # Pause to give user a chance to interrupt
        pycom.rgbled(0x222222)
        _logger.info("Pausing before continuing. If you want to interrupt, now is a good time.")
        for _ in range(0, 50):
            time.sleep_ms(100)
        pycom.rgbled(0x0)

        return 0

    elif next_state == STATE_SCHEDULE:
        _logger.info("Scheduling only....")
        return schedule_wake()

    try:
        hw.sync_to_most_reliable_rtc()
    except Exception as e:
        _logger.warning(e)

    if next_state == STATE_UPDATE:
        _logger.info("Starting check for updates...")

        hw.mount_sd_card()

        # If there is a crash during update, go back to hardware test
        next_state_on_boot(STATE_QUICK_HW_TEST)

        # Set persistent settings
        pycom.wifi_on_boot(False)
        pycom.lte_modem_en_on_boot(False)
        pycom.wdt_on_boot(False)
        pycom.heartbeat_on_boot(False)

        # Check for updates
        import co2unit_update
        updates_dir = hw.SDCARD_MOUNT_POINT + "/updates"
        updates_installed = co2unit_update.check_and_install_updates(updates_dir)

        if updates_installed:
            _logger.info("Updates installed, rebooting to hardware test")
            next_state_on_boot(STATE_QUICK_HW_TEST)
            return 0
        else:
            _logger.info("No updates installed, continuing to LTE test")
            next_state_on_boot(STATE_LTE_TEST)
            return 0

    elif next_state == STATE_TAKE_MEASUREMENT:
        _logger.info("Starting measurement sequence...")

        import co2unit_measure
        reading = co2unit_measure.read_sensors(hw)
        _logger.info("Reading: %s", reading)

        hw.mount_sd_card()

        reading_data_dir = hw.SDCARD_MOUNT_POINT + "/data/readings"
        co2unit_measure.store_reading(reading, reading_data_dir)

    elif next_state == STATE_COMMUNICATE:
        _logger.info("Starting communication sequence...")

        # TODO: set WDT at beginning for all paths
        wdt = machine.WDT(timeout=30*60*1000)

        hw.mount_sd_card()

        import co2unit_comm
        lte = co2unit_comm.transmit_data(hw, wdt)

    # Go to sleep until next wake-up
    return schedule_wake()
