try:
    import sys
    import machine
    import pycom
except:
    import mock_apis
    machine = mock_apis.MockMachine()
    sys = mock_apis.MockSys()
    pycom = mock_apis.MockPycom()

import logging
_logger = logging.getLogger("main")
_logger.setLevel(logging.DEBUG)

RUNNING_WDT_MS = 1000*60*2
REPL_WDT_MS = 1000*60*60*24
LAST_RESORT_DEEPSLEEP_MS = 1000*60*15

class NoopWdt(object):
    def feed(self):
        pass

wdt = NoopWdt()

class MainWrapper(object):
    """ Top-level run behavior

    - Suppress exceptions (except KeyboardInterrupt) so that unhandled errors
      do not cause exit to REPL
    - Instead, go into deep sleep for a specified amount of time as a last resort
    - Initialize watchdog timer (extend on KeyboardInterrupt exit to REPL)
    """

    def __enter__(self):
        _logger.info("Entering MainWrapper. Initializing WDT (%d ms)", RUNNING_WDT_MS)
        global wdt
        wdt = machine.WDT(timeout=RUNNING_WDT_MS)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type == KeyboardInterrupt:
            _logger.info("KeyboardInterrupt detected. Extending WDT (%d ms) and exiting to REPL.", REPL_WDT_MS)
            global wdt
            wdt.init(REPL_WDT_MS)
            sys.exit()
            return False

        if exc_val:
            _logger.exc(exc_val, "Uncaught exception at MainWrapper top level")

        _logger.warning("MainWrapper last resort. Don't know what else to do. Going to sleep for a while (%d ms).", LAST_RESORT_DEEPSLEEP_MS)
        machine.deepsleep(LAST_RESORT_DEEPSLEEP_MS)
        return False

class TaskRunner(object):

    def __init__(self):
        self.queue = []
        self.history = []

    def run_next_task(self):
        _logger.info("Task queue: %s", self.queue)
        task = self.queue[0]
        self.queue = self.queue[1:]

        instance = task() if isinstance(task, type) else task
        result = None
        _logger.info("Task %s START", instance)
        try:
            result = instance.run()
            _logger.info("Task %s OK", instance)
            self.history.append(instance)
        except KeyboardInterrupt:
            raise
        except:
            _logger.exception("Task %s FAIL", instance)

        if result:
            result = [result] if not isinstance(result, list) else result
            _logger.info("Got new tasks %s", result)
            self.queue = result + self.queue

    def run(self, *tasks):
        self.queue += tasks
        while self.queue:
            wdt.feed()
            self.run_next_task()

# Tasks
# ==================================================

class BootUp(object):
    def run(self):
        reset_cause = machine.reset_cause()

        if reset_cause == machine.PWRON_RESET:
            _logger.info("Manual reset")
            #return [InitPeripherals, LteTest]
            return [InitPeripherals,
                    QuickSelfTest, LteTest,
                    Communicate, CheckForUpdates,
                    SleepUntilScheduled]
        else:
            return [InitPeripherals, CheckForUpdates,
                    CheckSchedule, SleepUntilScheduled]

hw = None

class InitPeripherals(object):
    def run(self):
        global hw
        import co2unit_hw
        import time
        hw = co2unit_hw.Co2UnitHw()

        # Turn on peripherals
        hw.power_peripherals(True)
        # Trying to access the SD card too quickly often results in IO errors
        _logger.info("Giving hardware a moment after power on")
        time.sleep_ms(100)

# Self Tests
# --------------------------------------------------

class QuickSelfTest(object):
    def run(self):
        import co2unit_self_test
        co2unit_self_test.wdt = wdt
        co2unit_self_test.quick_test_hw(hw)

class LteTest(object):
    def run(self):
        import co2unit_self_test
        import time
        # Trying to access LTE too quickly after a reset will put the modem in
        # an error state.
        _logger.info("Giving modem a few moments to boot")
        time.sleep(20)
        co2unit_self_test.wdt = wdt
        co2unit_self_test.test_lte_ntp(hw)

# Actual Operation
# --------------------------------------------------

class TakeMeasurement(object):
    def run(self):
        try:
            flash_count = pycom.nvs_get("co2_flash_count")
        except ValueError:
            return 0

        import co2unit_measure
        co2unit_measure.wdt = wdt
        co2unit_measure.measure_sequence(hw, flash_count=flash_count)

        _logger.info("Resetting flash count after recording it")
        pycom.nvs_set("co2_flash_count")

class Communicate(object):
    def run(self):
        import co2unit_comm
        co2unit_comm.wdt = wdt
        lte, got_updates = co2unit_comm.comm_sequence(hw)

# Updates
# --------------------------------------------------

class CheckForUpdates(object):
    def run(self):
        import co2unit_update
        co2unit_update.wdt = wdt
        updated = co2unit_update.update_sequence(hw)
        if updated:
            return Communicate

# Scheduling
# --------------------------------------------------

SCHEDULE_PATH = "conf/schedule.json"

SCHEDULE_DEFAULT = [
            #["TakeMeasurement", 'minutes', 30, 0],
            #["Communicate", 'daily', 3, 15],
            ["TakeMeasurement", 'minutes', 5, 0],
            ["Communicate", 'minutes', 10, 2],
            ]

TASK_STRS = {
        "TakeMeasurement": TakeMeasurement,
        "Communicate": Communicate,
        }

class CheckSchedule(object):
    def runwith(self, itt=None, sched_cfg=None):
        import schedule

        _logger.info("Current time: %s", itt)

        sched = schedule.Schedule(sched_cfg)
        for task, task_sched in sched.sched:
            _logger.info("Schedule item: %s, %s", task, task_sched)

        tasks = sched.check(itt)
        _logger.info("Time to %s", tasks)

        task_objs = []
        for task_str in tasks:
            if task_str in TASK_STRS:
                task_objs.append( TASK_STRS[task_str] )
            else:
                _logger.warning("Configured task \"%s\" unknown. Ignoring.", task_str)

        return task_objs

    def run(self):
        import utime
        hw.sync_to_most_reliable_rtc(reset_ok=True)
        itt = utime.localtime()
        return self.runwith(itt=itt, sched_cfg=SCHEDULE_DEFAULT)

class SleepUntilScheduled(object):

    def runwith(self, tt=None, sched_cfg=None):
        import schedule
        import timeutil

        _logger.info("Current time: %s", tt)

        sched = schedule.Schedule(sched_cfg)
        agenda = sched.next(tt)

        for next_tt, task in agenda:
            secs = timeutil.mktime(next_tt) - timeutil.mktime(tt)
            _logger.info("At  {next_tt!s:32} (T minus {secs:5d} seconds), {task}".format(next_tt=next_tt, task=task, secs=secs))

        next_tt, task = agenda[0]
        secs = timeutil.mktime(next_tt) - timeutil.mktime(tt)

        _logger.info("Preparing for shutdown")
        hw.prepare_for_shutdown()

        _logger.info("Sleeping %d seconds until %s", secs, task)
        machine.deepsleep(secs * 1000)

    def run(self):
        import utime
        tt = utime.localtime()
        sched = SCHEDULE_DEFAULT
        return self.runwith(tt=tt, sched_cfg=SCHEDULE_DEFAULT)
