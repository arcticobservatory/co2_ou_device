import machine
import pycom
import time

import logging
_logger = logging.getLogger("co2unit_main")

import co2unit_hw
import pycom_util

# Normal operation
STATE_UNKNOWN           = const(0)
STATE_SELF_TEST         = const(1)
STATE_TAKE_MEASUREMENT  = const(2)
STATE_COMMUNICATE       = const(3)

MEASURE_FREQ_MINUTES = 5
COMM_SCHEDULE_HOUR = None
COMM_SCHEDULE_MINUTE = 7

next_state_on_boot = pycom_util.mk_on_boot_fn("co2_wake_next", default=STATE_UNKNOWN)

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
        return STATE_SELF_TEST

    if reset_cause in [machine.SOFT_RESET, machine.WDT_RESET]:
        _logger.info("Soft reset or self-reset")
        _logger.info("Checking scheduled action...")
        return STATE_UNKNOWN

    if reset_cause == machine.DEEPSLEEP_RESET:
        _logger.info("Woke up from deep sleep")
        scheduled = next_state_on_boot()
        if scheduled == STATE_UNKNOWN:
            _logger.warning("Woke from deep sleep, but no activity scheduled. Possible crash.")
        return scheduled

    _logger.warning("Unknown wake circumstances")
    return STATE_UNKNOWN

def run(hw, next_state, hw_test_only=False):

    try:
        # Clear wake hints so we can detect a crash
        next_state_on_boot(erase=True)

        if next_state == STATE_UNKNOWN:
            _logger.warning("Unknown start state. Defaulting to measurement.")
            next_state = STATE_TAKE_MEASUREMENT

        # Run chosen state
        # --------------------------------------------------

        # Turn on peripherals
        hw.power_peripherals(True)

        if next_state == STATE_SELF_TEST:
            _logger.info("Starting quick self test...")

            # Reset heartbeat to initialize RGB LED, for test feedback
            pycom.heartbeat(True)
            pycom.heartbeat(False)

            # Do self-test
            import co2unit_self_test
            co2unit_self_test.quick_test_hw(hw)

            # If SD card is OK, mount it
            if not co2unit_self_test.failures & co2unit_self_test.FLAG_SD_CARD:
                import os
                os.mount(hw.sdcard(), hw.SDCARD_MOUNT_POINT)

            # Pause to give user a chance to interrupt
            pycom.rgbled(0x222222)
            _logger.info("Pausing before continuing. If you want to interrupt, now is a good time.")
            try:
                for _ in range(0, 50):
                    time.sleep_ms(100)
            except KeyboardInterrupt:
                _logger.info("Caught interrupt. Exiting to REPL")
                pycom.rgbled(0x0)
                import sys
                sys.exit()
            pycom.rgbled(0x0)

            if not hw_test_only:

                # If SD card is OK, check for updates
                if not co2unit_self_test.failures & co2unit_self_test.FLAG_SD_CARD:
                    import co2unit_update
                    updates_dir = hw.SDCARD_MOUNT_POINT + "/updates"
                    updates_installed = co2unit_update.check_and_install_updates(updates_dir)

                    if updates_installed:
                        # Reboot and restart self test
                        next_state_on_boot(STATE_SELF_TEST)
                        machine.reset()

                # Continue with self test
                co2unit_self_test.test_lte_ntp(hw)

            # Set persistent settings
            pycom.wifi_on_boot(False)
            pycom.lte_modem_en_on_boot(False)
            pycom.wdt_on_boot(False)
            pycom.heartbeat_on_boot(False)

        elif next_state == STATE_TAKE_MEASUREMENT:
            _logger.info("Starting measurement sequence...")

            try:
                hw.sync_to_most_reliable_rtc()
            except Exception as e:
                _logger.warning("%s: %s", type(e).__name__, e)

            import co2unit_measure
            reading = co2unit_measure.read_sensors(hw)
            _logger.info("Reading: %s", reading)

            import os
            os.mount(hw.sdcard(), hw.SDCARD_MOUNT_POINT)

            reading_data_dir = hw.SDCARD_MOUNT_POINT + "/data/readings"
            co2unit_measure.store_reading(reading, reading_data_dir)

        elif next_state == STATE_COMMUNICATE:
            _logger.info("Starting communication sequence...")

            try:
                hw.sync_to_most_reliable_rtc()
            except Exception as e:
                _logger.warning("%s: %s", type(e).__name__, e)

            import os
            os.mount(hw.sdcard(), hw.SDCARD_MOUNT_POINT)

            # TODO: set WDT at beginning for all paths
            wdt = machine.WDT(timeout=30*60*1000)

            import co2unit_comm
            lte = co2unit_comm.transmit_data(hw, wdt)

    #except Exception as e:
        # TODO: catch any exception
    finally: pass

    # Go to sleep until next wake-up
    try:
        hw.power_peripherals(False)
        _logger.info("Peripherals off")
    except Exception(e):
        _logger.error("Could not turn off peripherals before sleep. %s: %s", type(e).__name__, e)

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
        _logger.info("Sleeping...")
        machine.deepsleep(seconds_until_comm * 1000)

    else:
        _logger.info("Measurement next")
        next_state_on_boot(STATE_TAKE_MEASUREMENT)
        _logger.info("Sleeping...")
        machine.deepsleep(seconds_until_measure * 1000)

    # MicroPython does not resume after deep sleep.
    # Function will never return.
    # Machine will reboot after sleep.
