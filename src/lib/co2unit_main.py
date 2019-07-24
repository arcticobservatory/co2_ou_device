import machine
import pycom
import time

import logging
_logger = logging.getLogger("co2unit_main")

import co2unit_hw
import configutil
import pycom_util

# Normal operation
STATE_UNKNOWN           = const(0)
STATE_CRASH_RECOVERY    = const(1)
STATE_QUICK_HW_TEST     = const(2)
STATE_LTE_TEST          = const(3)
STATE_UPDATE            = const(4)
STATE_SCHEDULE          = const(5)
STATE_MEASURE           = const(6)
STATE_COMMUNICATE       = const(7)

SCHED_MINUTES   = const(0)
SCHED_DAILY     = const(1)

SCHEDULE_DEFAULT = {
        "tasks": [
            [SCHED_MINUTES, 30, 0, STATE_MEASURE],
            [SCHED_DAILY, 3, 10, STATE_COMMUNICATE],
            ]
        }

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
        return STATE_QUICK_HW_TEST

    if reset_cause in [machine.SOFT_RESET, machine.WDT_RESET, machine.DEEPSLEEP_RESET]:
        if reset_cause == machine.SOFT_RESET:
            _logger.info("Soft reset")
        elif reset_cause == machine.WDT_RESET:
            _logger.info("Self-reset or watchdog reset")
        elif reset_cause == machine.DEEPSLEEP_RESET:
            _logger.info("Woke up from deep sleep")

        # TODO: On recovery from crash, make sure modem is off

        _logger.info("Checking scheduled action...")
        scheduled = next_state_on_boot(default=STATE_CRASH_RECOVERY)
        return scheduled

    _logger.warning("Unknown wake circumstances")
    return STATE_UNKNOWN

def crash_recovery_sequence():
    _logger.info("Starting crash recovery sequence...")
    wdt = machine.WDT(timeout=10*1000)
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

    try:
        schedule_path = "/".join([hw.SDCARD_MOUNT_POINT, SCHEDULE_PATH])
        schedule = configutil.read_config_json(schedule_path, SCHEDULE_DEFAULT)
    except Exception as e:
        _logger.exc(e, "Could not read schdule config %s. Falling back to defaults", SCHEDULE_PATH)
        schedule = SCHEDULE_DEFAULT
    _logger.info("Schedule: %s", schedule)

    tasks = schedule.tasks

    _logger.info("Now %s", time.gmtime())

    countdowns = []
    for item in tasks:
        sched_type = item[0]
        if sched_type == SCHED_MINUTES:
            _, minutes, offset, action = item
            item_time = timeutil.next_even_minutes(minutes, plus=offset)
        elif sched_type == SCHED_DAILY:
            _, hour, minutes, action = item
            item_time = timeutil.next_time_of_day(hour, minutes)
        else:
            raise Exception("Unknown scedule type {}".format(sched_type))

        seconds_left = timeutil.seconds_until_time(item_time)
        countdowns.append([seconds_left, item_time, action])

    countdowns.sort(key=lambda x:x[0])

    for c in countdowns:
        _logger.info("At  {1!s:32} (T minus {0:5d} seconds), state {2:#04x}".format(*c))

    sleep_sec, _, action = countdowns[0]
    next_state_on_boot(action)
    return sleep_sec * 1000

def run(hw, next_state):
    # In case of unexpected reset, go to crash recovery
    next_state_on_boot(STATE_CRASH_RECOVERY)

    if next_state == STATE_UNKNOWN:
        _logger.warning("Unknown start state. Default to crash recovery")
        next_state = STATE_CRASH_RECOVERY

    # Turn on peripherals
    hw.power_peripherals(True)

    # Self-test states
    # --------------------------------------------------

    if next_state == STATE_CRASH_RECOVERY:
        crash_recovery_sequence()
        next_state_on_boot(STATE_SCHEDULE)
        return 0

    if next_state in [STATE_QUICK_HW_TEST, STATE_LTE_TEST]:
        # Reset heartbeat to initialize RGB LED, for test feedback
        reset_rgbled()

        # Do self-test
        import co2unit_self_test

        if next_state == STATE_QUICK_HW_TEST:
            co2unit_self_test.quick_test_hw(hw)
            next_state_on_boot(STATE_LTE_TEST)

        elif next_state == STATE_LTE_TEST:
            co2unit_self_test.test_lte_ntp(hw)
            next_state_on_boot(STATE_UPDATE)

        # Pause to give user a chance to interrupt
        pycom.rgbled(0x0)
        _logger.info("Pausing before continuing. If you want to interrupt, now is a good time.")
        for _ in range(0, 50):
            time.sleep_ms(100)

        return 0

    # States that require RTC
    # --------------------------------------------------

    try:
        hw.sync_to_most_reliable_rtc()
    except Exception as e:
        _logger.warning(e)

    # States that require SD card
    # --------------------------------------------------

    hw.mount_sd_card()

    if next_state == STATE_SCHEDULE:
        _logger.info("Scheduling only....")
        return schedule_wake(hw)

    if next_state == STATE_UPDATE:
        # Set persistent settings
        set_persistent_settings()

        # Check for updates
        import co2unit_update
        co2unit_update.update_sequence(hw.SDCARD_MOUNT_POINT)

    if next_state == STATE_MEASURE:
        import co2unit_measure
        co2unit_measure.measure_sequence(hw)

    if next_state == STATE_COMMUNICATE:
        import co2unit_comm
        lte = co2unit_comm.comm_sequence(hw)

    # Go to sleep until next wake-up
    return schedule_wake(hw)
