import machine
import pycom
import time

import logging
_logger = logging.getLogger("co2unit_main")

import pycom_util
import timeutil

wdt = timeutil.DummyWdt()

# Run states
STATE_UNKNOWN           = const(0)
STATE_CRASH_RECOVERY    = const(1)
STATE_QUICK_HW_TEST     = const(2)
STATE_LTE_TEST          = const(3)
STATE_UPDATE            = const(4)
STATE_SCHEDULE          = const(5)
STATE_MEASURE           = const(6)
STATE_COMMUNICATE       = const(7)
STATE_RECORD_FLASH      = const(8)

# Nonvolatile memory accessors
next_state_on_boot = pycom_util.mk_on_boot_fn("co2_wake_next")
nv_flash_count = pycom_util.mk_on_boot_fn("co2_flash_count", default=0)

# Scheduling

SCHEDULE_PATH = "conf/schedule.json"

SCHEDULE_TYPES = {
        "minutes": timeutil.next_even_minutes,
        "daily": timeutil.next_time_of_day,
        "minutes_random": timeutil.next_minutes_random,
        "daily_random": timeutil.next_time_of_day_random,
        }

SCHEDULE_DEFAULT = {
        "tasks": [
            [STATE_MEASURE, 'minutes', 30, 0],
            [STATE_COMMUNICATE, 'daily_random', 3, 2, 25],
            ]
        }

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

def record_flash(hw):
    _logger.info("Recording detected IR flash...")
    fc = nv_flash_count()
    fc += 1
    nv_flash_count(fc)
    _logger.info("New flash count: %d", fc)

def crash_recovery_sequence(hw):
    _logger.info("Starting crash recovery sequence...")

    try:
        import co2unit_errors
        co2unit_errors.warning(hw, "Had to run recovery procedure. Watchdog reset?")
    except Exception as e:
        _logger.exc(e, "Could not log warning")

    try:
        _logger.info("Making sure LTE modem is off")

        # LTE init seems to be successful more often if we give it time first
        time.sleep_ms(1000)

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

def set_persistent_settings():
    _logger.info("Setting persistent settings...")
    pycom.wifi_on_boot(False)
    pycom.lte_modem_en_on_boot(False)
    pycom.heartbeat_on_boot(False)
    pycom.wdt_on_boot(True)
    pycom.wdt_on_boot_timeout(10*1000)

def schedule_countdowns(tasks):
    _logger.info("Now %s", time.gmtime())

    countdowns = []
    for item in tasks:
        action, sched_type, *args = item
        if sched_type in SCHEDULE_TYPES:
            item_time = SCHEDULE_TYPES[sched_type](*args)
        else:
            raise Exception("Unknown schedule type {} in {}".format(sched_type, item))

        seconds_left = timeutil.seconds_until_time(item_time)
        # Normalize time tuple before displaying it (handle rollover)
        item_time = time.gmtime(time.mktime(item_time))
        countdowns.append([seconds_left, item_time, action])

    countdowns.sort(key=lambda x:x[0])

    for c in countdowns:
        _logger.info("At  {1!s:32} (T minus {0:5d} seconds), state {2:#04x}".format(*c))

    return countdowns

def schedule_wake(hw):
    import configutil

    hw.sync_to_most_reliable_rtc(reset_ok=True)
    hw.mount_sd_card()

    try:
        schedule_path = "/".join([hw.SDCARD_MOUNT_POINT, SCHEDULE_PATH])
        schedule = configutil.read_config_json(schedule_path, SCHEDULE_DEFAULT)
    except Exception as e:
        _logger.exc(e, "Could not read schdule config %s. Falling back to defaults", SCHEDULE_PATH)
        schedule = SCHEDULE_DEFAULT

    _logger.info("Schedule: %s", schedule)

    countdowns = schedule_countdowns(schedule.tasks)
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

    if run_state == STATE_CRASH_RECOVERY:
        crash_recovery_sequence(hw)
        return (0, STATE_SCHEDULE)

    if run_state == STATE_QUICK_HW_TEST:
        import co2unit_self_test
        co2unit_self_test.wdt = wdt
        co2unit_self_test.quick_test_hw(hw)
        return (0, STATE_LTE_TEST)

    if run_state == STATE_LTE_TEST:
        import co2unit_self_test
        co2unit_self_test.wdt = wdt
        co2unit_self_test.test_lte_ntp(hw)
        return (0, STATE_UPDATE)

    if run_state == STATE_SCHEDULE:
        _logger.info("Scheduling only....")
        return schedule_wake(hw)

    if run_state == STATE_UPDATE:
        set_persistent_settings()

        import co2unit_update
        co2unit_update.wdt = wdt
        updated = co2unit_update.update_sequence(hw)
        # After update, try communicating again so we know it worked
        return (0, STATE_COMMUNICATE)

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
        lte, got_updates = co2unit_comm.comm_sequence(hw)
        if got_updates:
            _logger.info("Updates downloaded")
            return (0, STATE_UPDATE)

    return schedule_wake(hw)
