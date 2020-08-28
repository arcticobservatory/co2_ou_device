import ustruct
import utime

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

def nvs_get_default(key, default=None):
    try:
        val = pycom.nvs_get(key)
        if val == None:
            val = default
        return val
    except ValueError:
        return default

def nvs_erase_idempotent(key):
    try:
        pycom.nvs_erase(key)
    except KeyError:
        pass

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

class NvsTaskLog(object):

    TASK_NONE = -1
    TASK_UNKNOWN = -2

    STAT_STRS = [None, "START","OK","FAIL"]
    KEY_PREFIX = "task_log_"
    LOG_LEN = 16

    NULL_EVENT = (None, None, 0)

    def __init__(self):
        self.registry = []

    def register(self, task):
        self.registry.append(task)

    def _pack_event(self, task, status, repetitions):
        if task == None:
            taskid = self.TASK_NONE
        elif task in self.registry:
            taskid = self.registry.index(task)
        else:
            taskid = self.TASK_UNKNOWN

        status = self.STAT_STRS.index(status)

        if repetitions > 255:
            repetitions = 255

        b = ustruct.pack("hBB", taskid, status, repetitions)
        i = ustruct.unpack("I", b)[0]
        return i

    def _unpack_event(self, packed):
        if packed == None:
            return self.NULL_EVENT

        b = ustruct.pack("I", packed)
        taskid, status, repetitions = ustruct.unpack("hBB", b)

        if taskid == self.TASK_NONE:
            task = None
        elif taskid == self.TASK_UNKNOWN:
            task = "UNKNOWN_TASK"
        elif taskid < len(self.registry):
            task = self.registry[taskid]
        else:
            task = taskid

        status = self.STAT_STRS[status]
        return task, status, repetitions

    def _key_str(self, i):
        return "{}{:03d}".format(self.KEY_PREFIX, i)

    def _persist_run_log(self, log):
        for i, event in enumerate(log):
            key = self._key_str(i)
            packed = self._pack_event(*event)
            pycom.nvs_set(key, packed)

    def read_run_log(self):
        log = []
        for i in range(0, self.LOG_LEN):
            key = self._key_str(i)
            packed = nvs_get_default(key, default=None)
            event = self._unpack_event(packed)
            if event != self.NULL_EVENT:
                log.append(event)
        return log

    def _record_event(self, task, status):
        log = self.read_run_log()

        if log and log[0][0:2] == (task, status):
            log[0] = (task, status, log[0][2]+1)
        else:
            if len(log) >= self.LOG_LEN:
                log = log[1:]
            log.append( (task,status,1) )

        self._persist_run_log(log)

    def reset_log(self):
        for i in range(0, self.LOG_LEN):
            key = self._key_str(i)
            nvs_erase_idempotent(key)

    def record_start(self, task): self._record_event(task, "START")
    def record_ok(self, task): self._record_event(task, "OK")
    def record_fail(self, task): self._record_event(task, "FAIL")

nvs_task_log = NvsTaskLog()

class TaskRunner(object):

    def __init__(self):
        self.queue = []
        self.history = []

    def run_next_task(self):
        task = self.queue[0]
        self.queue = self.queue[1:]

        for event in nvs_task_log.read_run_log():
            _logger.info("PREVIOUSLY: %-30s %-5s %3d", *event)
        _logger.info("NEXT      : %s", task)
        for t in self.queue:
            _logger.info("THEN      : %s", t)

        instance = task() if isinstance(task, type) else task
        result = None
        _logger.info("=== Task %s START ===", instance)
        nvs_task_log.record_start(task)
        try:
            result = instance.run()
            _logger.info("=== Task %s OK ===", instance)
            nvs_task_log.record_ok(task)
            self.history.append(instance)
        except KeyboardInterrupt:
            raise
        except:
            _logger.exception("=== Task %s FAIL ===", instance)
            nvs_task_log.record_fail(task)

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
                    Communicate, CheckForUpdates]

        elif reset_cause == machine.DEEPSLEEP_RESET:
            return [InitPeripherals, CheckForUpdates, CheckSchedule]

        elif reset_cause == machine.SOFT_RESET:
            # Pressed CTRL+D on console. Good for testing sequences.
            return [InitPeripherals, CrashRecovery]
            #return [InitPeripherals, CheckSchedule]

        elif reset_cause == machine.WDT_RESET or True:
            # WDT_REST also seems to apply to machine.reset() in script
            return [InitPeripherals, CrashRecovery]

nvs_task_log.register(BootUp)

hw = None

class InitPeripherals(object):
    def run(self):
        import co2unit_hw
        import time
        global hw
        hw = co2unit_hw.Co2UnitHw()

        # Turn on peripherals
        hw.power_peripherals(True)
        # Trying to access the SD card too quickly often results in IO errors
        _logger.info("Giving hardware a moment after power on")
        time.sleep_ms(100)

nvs_task_log.register(InitPeripherals)

class CrashRecovery(object):
    def run(self):
        import time
        global hw

        entrycount = nvs_get_default("recover_count", 0)
        entrycount += 1
        pycom.nvs_set("recover_count", entrycount)

        _logger.info("CRASH RECOVERY. This is recovery attempt %s", entrycount)

        if entrycount > 5:
            _logger.error("Too many recovery attempts (%s). Giving up.", entrycount)
            return

        lte_was_on = nvs_get_default("lte_on", False)
        lte_turned_off = False

        if lte_was_on:
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
                lte_turned_off = True
                pycom.nvs_set("lte_on", False)
            except Exception as e:
                _logger.exc(e, "Could not turn off LTE modem")

        try:
            import co2unit_errors
            co2unit_errors.warning(hw, "CRASH RECOVERY. Running recovery procedure (attempt %d). Watchdog reset? LTE was on: %s; LTE turned off: %s" % (entrycount, lte_was_on, lte_turned_off) )
            co2unit_errors.info(hw, "Run log leading up to this... %s" % (nvs_task_log.read_run_log(),) )
        except Exception as e:
            _logger.exc(e, "Could not log warning")

        pycom.nvs_set("recover_count", 0)

nvs_task_log.register(CrashRecovery)

# Self Tests
# --------------------------------------------------

class QuickSelfTest(object):
    def run(self):
        import co2unit_self_test
        co2unit_self_test.wdt = wdt
        co2unit_self_test.quick_test_hw(hw)

nvs_task_log.register(QuickSelfTest)

class LteTest(object):
    def run(self):
        import co2unit_self_test
        import time
        co2unit_self_test.wdt = wdt
        co2unit_self_test.test_lte_ntp(hw)

nvs_task_log.register(LteTest)

# Actual Operation
# --------------------------------------------------

class TakeMeasurement(object):
    def run(self):
        flash_count = nvs_get_default("co2_flash_count", 0)

        import co2unit_measure
        co2unit_measure.wdt = wdt
        co2unit_measure.measure_sequence(hw, flash_count=flash_count)

        _logger.info("Resetting flash count after recording it")
        pycom.nvs_set("co2_flash_count", flash_count)

nvs_task_log.register(TakeMeasurement)

class Communicate(object):
    def run(self):
        import co2unit_comm
        co2unit_comm.wdt = wdt
        lte, got_updates = co2unit_comm.comm_sequence(hw)
        return [CheckForUpdates]

nvs_task_log.register(Communicate)

# Updates
# --------------------------------------------------

def set_persistent_settings():
    _logger.info("Setting persistent settings...")
    pycom.wifi_on_boot(False)
    pycom.lte_modem_en_on_boot(False)
    pycom.heartbeat_on_boot(False)
    pycom.wdt_on_boot(True)
    pycom.wdt_on_boot_timeout(RUNNING_WDT_MS)

class CheckForUpdates(object):
    def run(self):
        set_persistent_settings()
        import co2unit_update
        co2unit_update.wdt = wdt
        updated = co2unit_update.update_sequence(hw)
        if updated:
            return Communicate

nvs_task_log.register(CheckForUpdates)

# Scheduling
# --------------------------------------------------

SCHEDULE_PATH = "conf/schedule.json"

SCHEDULE_DEFAULT = [
            ["TakeMeasurement", 'minutes', 30, 0],
            ["Communicate", 'daily', 3, 15],
            #["TakeMeasurement", 'minutes', 10, 0],
            #["Communicate", 'minutes', 30, 2],
            ]

TASK_STRS = {
        "TakeMeasurement": TakeMeasurement,
        "Communicate": Communicate,
        }

class CheckSchedule(object):
    def runwith(self, itt, sched_cfg, ett=None):
        import schedule

        _logger.info("Current time (interal  RTC): %s", itt)
        _logger.info("Current time (external RTC): %s", ett)

        sched = schedule.Schedule(sched_cfg)
        for task, task_sched in sched.sched:
            _logger.info("Schedule item: %s, %s", task, task_sched)

        tasks = sched.check(itt)
        if ett:
            etasks = sched.check(ett)
            if tasks != etasks:
                if ett < itt:
                    _logger.info("Scheduled to run %s, but we are early. Going by external time: %s.", tasks, etasks)
                    tasks = etasks
                else:
                    _logger.info("Scheduled to run %s, but we are late. Running those tasks.", tasks)

        if ett and ett < itt:
            etasks = sched.check(ett)
            if tasks != etasks:
                _logger.info("Scheduled to run %s, but we are early. Going by external time: %s.", tasks, etasks)
                tasks = etasks

        _logger.info("Scheduled to run %s", tasks)

        task_objs = []
        for task_str in tasks:
            if task_str in TASK_STRS:
                task_objs.append( TASK_STRS[task_str] )
            else:
                _logger.warning("Configured task \"%s\" unknown. Ignoring.", task_str)

        return task_objs

    def run(self):
        import utime
        itt = utime.localtime()
        ett = hw.ertc.get_time()
        hw.sync_to_most_reliable_rtc(reset_ok=True)
        return self.runwith(itt=itt, ett=ett, sched_cfg=SCHEDULE_DEFAULT)

nvs_task_log.register(CheckSchedule)

class SleepUntilScheduled(object):

    MIN_DEEPSLEEP_MS = 1000 * 20

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
        ms = secs * 1000

        # Deep sleep is not really worth it for less than ~30 sec.
        # Instead, light sleep and then go back to checking the schedule.
        if ms < self.MIN_DEEPSLEEP_MS:
            _logger.info("Light sleeping only %d seconds until %s", secs, task)
            utime.sleep_ms(ms)
            return [CheckSchedule, SleepUntilScheduled]

        if hw:
            _logger.info("Preparing for shutdown")
            hw.prepare_for_shutdown()

        _logger.info("Sleeping %d seconds until %s", secs, task)
        machine.deepsleep(ms)

    def run(self):
        import utime
        tt = utime.localtime()
        sched = SCHEDULE_DEFAULT
        return self.runwith(tt=tt, sched_cfg=SCHEDULE_DEFAULT)

nvs_task_log.register(SleepUntilScheduled)
