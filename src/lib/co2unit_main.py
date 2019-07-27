import machine
import pycom
import time

import logging
_logger = logging.getLogger("co2unit_main")

import pycom_util
import timeutil

# Normal operation
STATE_UNKNOWN           = const(0)
STATE_CRASH_RECOVERY    = const(1)
STATE_QUICK_HW_TEST     = const(2)
STATE_LTE_TEST          = const(3)
STATE_UPDATE            = const(4)
STATE_SCHEDULE          = const(5)
STATE_MEASURE           = const(6)
STATE_COMMUNICATE       = const(7)
STATE_RECORD_FLASH      = const(8)

SCHED_MINUTES   = const(0)
SCHED_DAILY     = const(1)

SCHEDULE_DEFAULT = {
        "tasks": [
            [STATE_MEASURE, 'minutes', 30, 0],
            [STATE_COMMUNICATE, 'daily', 3, 10],
            ]
        }

next_state_on_boot = pycom_util.mk_on_boot_fn("co2_wake_next")
nv_flash_count = pycom_util.mk_on_boot_fn("co2_flash_count", default=0)

wdt = timeutil.DummyWdt()

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
        return STATE_QUICK_HW_TEST

    if reset_cause in [machine.SOFT_RESET, machine.WDT_RESET, machine.DEEPSLEEP_RESET]:
        if reset_cause == machine.SOFT_RESET:
            _logger.info("Soft reset")
        elif reset_cause == machine.WDT_RESET:
            _logger.info("Self-reset or watchdog reset")
        elif reset_cause == machine.DEEPSLEEP_RESET:
            wake_reason = machine.wake_reason()
            _logger.info("Woke up from deep sleep. Reason %s", wake_reason)
            if wake_reason[0] == machine.PIN_WAKE:
                _logger.info("Woke via pin")
                return STATE_RECORD_FLASH

        # TODO: On recovery from crash, make sure modem is off

        scheduled = next_state_on_boot(default=STATE_CRASH_RECOVERY)
        _logger.info("Scheduled action 0x%02x", scheduled)
        return scheduled

    _logger.warning("Unknown wake circumstances")
    return STATE_UNKNOWN

def user_interrupt_countdown(secs=5):
    _logger.info("Pausing before continuing. If you want to interrupt, now is a good time.")
    print("Continuing in", end="")
    try:
        for i in reversed(range(1, secs+1)):
            print(" {}".format(i), end="")
            for _ in range(0,100):
                time.sleep_ms(10)
                wdt.feed()
    finally:
        print()

def record_flash(hw):
    _logger.info("Recording detected IR flash...")
    fc = nv_flash_count()
    fc += 1
    nv_flash_count(fc)
    _logger.info("New flash count: %d", fc)

def crash_recovery_sequence():
    _logger.info("Starting crash recovery sequence...")
    try:
        _logger.info("Making sure LTE modem is off")
        import network
        _logger.info("Initializing LTE just to get handle...")
        lte = network.LTE()
        wdt.feed()
        _logger.info("Deinit...")
        lte.deinit()
        wdt.feed()
        _logger.info("LTE off")
    except Exception as e:
        _logger.exc(e, "Could not turn off LTE modem")

def reset_rgbled():
    # When heartbeat is disabled at boot, calls to pycom.rgbled won't work.
    # Need to turn it on and off again to re-enable.
    pycom.heartbeat(True)
    pycom.heartbeat(False)

def set_persistent_settings():
    _logger.info("Setting persistent settings...")
    pycom.wifi_on_boot(False)
    pycom.lte_modem_en_on_boot(False)
    pycom.heartbeat_on_boot(False)
    pycom.wdt_on_boot(True)
    pycom.wdt_on_boot_timeout(10*1000)

SCHEDULE_PATH = "conf/schedule.json"

def schedule_wake(hw):
    import timeutil
    import configutil

    try:
        schedule_path = "/".join([hw.SDCARD_MOUNT_POINT, SCHEDULE_PATH])
        schedule = configutil.read_config_json(schedule_path, SCHEDULE_DEFAULT)
    except Exception as e:
        _logger.exc(e, "Could not read schdule config %s. Falling back to defaults", SCHEDULE_PATH)
        schedule = SCHEDULE_DEFAULT

    _logger.info("Schedule: %s", schedule)

    countdowns = timeutil.schedule_countdowns(schedule.tasks)
    sleep_sec, _, action = countdowns[0]
    return (sleep_sec * 1000, action)

def run(hw, run_state):
    if run_state == STATE_UNKNOWN:
        _logger.warning("Unknown start state. Default to crash recovery")
        run_state = STATE_CRASH_RECOVERY

    if run_state == STATE_RECORD_FLASH:
        record_flash(hw)
        remaining = machine.remaining_sleep_time()
        if remaining:
            scheduled_state = next_state_on_boot()
            _logger.info("Before-wake scheduled state: 0x%02x; Sleep remaining: %d ms", scheduled_state, remaining)
            return (remaining, scheduled_state)
        else:
            _logger.warning("Could not determine previous schedule before wake, rescheduling...")
            return (0, STATE_SCHEDULE)

    # In case of unexpected reset (e.g. watch-dog), go to crash recovery
    next_state_on_boot(STATE_CRASH_RECOVERY)

    # Turn on peripherals
    hw.power_peripherals(True)

    # Self-test states
    # --------------------------------------------------

    if run_state == STATE_CRASH_RECOVERY:
        crash_recovery_sequence()
        return (0, STATE_SCHEDULE)

    if run_state in [STATE_QUICK_HW_TEST, STATE_LTE_TEST]:
        # Reset heartbeat to initialize RGB LED, for test feedback
        reset_rgbled()

        import co2unit_self_test

        if run_state == STATE_QUICK_HW_TEST:
            co2unit_self_test.quick_test_hw(hw)
            retval = (0, STATE_LTE_TEST)

        elif run_state == STATE_LTE_TEST:
            co2unit_self_test.test_lte_ntp(hw)
            retval = (0, STATE_UPDATE)

        pycom.rgbled(0x0)
        user_interrupt_countdown()
        return retval

    # States that require RTC
    # --------------------------------------------------

    try:
        hw.sync_to_most_reliable_rtc()
    except Exception as e:
        _logger.warning(e)

    # States that require SD card
    # --------------------------------------------------

    hw.mount_sd_card()

    if run_state == STATE_SCHEDULE:
        _logger.info("Scheduling only....")
        return schedule_wake(hw)

    if run_state == STATE_UPDATE:
        # Set persistent settings
        set_persistent_settings()

        # Check for updates
        import co2unit_update
        co2unit_update.update_sequence(hw.SDCARD_MOUNT_POINT)

    if run_state == STATE_MEASURE:
        flash_count = nv_flash_count()
        import co2unit_measure
        co2unit_measure.wdt = wdt
        co2unit_measure.measure_sequence(hw, flash_count=flash_count)
        _logger.info("Resetting flash count after recording it")
        nv_flash_count(0)

    if run_state == STATE_COMMUNICATE:
        import co2unit_comm
        co2unit_comm.wdt = wdt
        co2unit_comm.comm_sequence(hw)

    # Go to sleep until next wake-up
    return schedule_wake(hw)
