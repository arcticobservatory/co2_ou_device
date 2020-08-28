import sys

import unittest
import logging

import timeutil
import mock_apis
import co2unit_main2 as main

# Suppress logging
logging.getLogger("mock_apis").setLevel(logging.CRITICAL)
logging.getLogger("main").setLevel(logging.CRITICAL)
logging.getLogger("main").exception = lambda *args: None
logging.getLogger("main").exc = lambda *args: None

class TestNoopWdt(unittest.TestCase):
    def test_noop_wdt(self):
        wdt = main.NoopWdt()
        wdt.feed()

class TestMainWrapper(unittest.TestCase):

    def setUp(self):
        main.machine = mock_apis.MockMachine()
        main.sys = mock_apis.MockSys()

    def test_normal_exit(self):
        with main.MainWrapper():
            pass
        self.assertTrue(main.machine._deepsleep_called)
        self.assertEqual(main.machine._deepsleep_time_ms, main.LAST_RESORT_DEEPSLEEP_MS)

    def test_exception_exit(self):
        class TestException(Exception):
            pass
        with self.assertRaises(TestException):
            with main.MainWrapper():
                raise TestException()
        self.assertTrue(main.machine._deepsleep_called)
        self.assertEqual(main.machine._deepsleep_time_ms, main.LAST_RESORT_DEEPSLEEP_MS)

    def test_keyboard_interrupt(self):
        with self.assertRaises(KeyboardInterrupt):
            with main.MainWrapper():
                raise KeyboardInterrupt()
        self.assertFalse(main.machine._deepsleep_called)
        self.assertTrue(main.sys._exit_called)

    def test_wdt_control(self):

        with self.assertRaises(KeyboardInterrupt):
            with main.MainWrapper() as mw:
                self.assertEqual(main.wdt._init_count, 1)
                self.assertEqual(main.wdt._init_timeout_ms, main.RUNNING_WDT_MS)
                raise KeyboardInterrupt()

        self.assertEqual(main.wdt._init_count, 2)
        self.assertEqual(main.wdt._init_timeout_ms, main.REPL_WDT_MS)

class TestTaskRunner(unittest.TestCase):

    def setUp(self):
        main.machine = mock_apis.MockMachine()
        main.sys = mock_apis.MockSys()

    def test_run_task(self):
        class MockTask(object):
            def __init__(self): self._was_run = False
            def run(self, **kwargs): self._was_run = True

        task = MockTask()

        runner = main.TaskRunner()
        runner.run(task)
        self.assertTrue(task._was_run)
        self.assertNotEqual(main.wdt._feed_count, 0, "WDT should have been fed")

    def test_accept_task_class(self):
        side_effect = {"was_run": False}
        class TaskClass(object):
            def run(self, **kwargs):
                side_effect["was_run"] = True

        runner = main.TaskRunner()
        runner.run(TaskClass)
        self.assertTrue(side_effect["was_run"])

    def test_error_in_context_manager(self):
        class BodyException(Exception): pass
        class ExitException(Exception): pass
        class BadManager(object):
            def __enter__(self):
                pass
            def __exit__(self, exc_type, exc_val, exc_tb):
                raise ExitException()

        with self.assertRaises(ExitException):
            with BadManager():
                raise BodyException()

    def test_suppress_error(self):
        class MockException(Exception): pass
        exc_val = MockException()

        class ErrorTask(object):
            def run(self, **kwargs):
                raise exc_val
        task = ErrorTask()

        runner = main.TaskRunner()
        try:
            runner.run(task)
        except MockException:
            self.fail("MockException should not be allowed to pass through")

        class KeyboardTask(object):
            def run(self, **kwargs):
                raise KeyboardInterrupt()

        with self.assertRaises(KeyboardInterrupt):
            runner.run(KeyboardTask)

    def test_get_next_task(self):
        class NextA(object):
            def run(self): pass
        class NextB(object):
            def run(self): pass
        class Last(object):
            def run(self): pass

        nexta = NextA()
        nextb = NextB()
        last_task = Last()

        class ReturnSingle(object):
            def run(self): return nexta
        class ReturnList(object):
            def run(self): return [nexta, nextb]

        returnsingle = ReturnSingle()
        returnlist = ReturnList()

        runner = main.TaskRunner()
        runner.run(returnsingle, last_task)
        self.assertEqual(runner.history, [returnsingle,nexta,last_task])

        runner = main.TaskRunner()
        runner.run(returnlist, last_task)
        self.assertEqual(runner.history, [returnlist,nexta,nextb,last_task])

class TestPycomNvsWithDefault(unittest.TestCase):
    def setUp(self):
        main.pycom = mock_apis.MockPycom()

    def test_nvs_with_default(self):
        main.pycom.nvs_set("test_nvs_key_asdf", 123)
        val = main.nvs_get_default("test_nvs_key_asdf", 456)
        self.assertEqual(val, 123)

        main.pycom.nvs_erase("test_nvs_key_asdf")
        val = main.nvs_get_default("test_nvs_key_asdf", 456)
        self.assertEqual(val, 456)

    def test_nvs_erase_idempotent(self):
        main.pycom.nvs_set("test_nvs_key_asdf", 123)
        main.nvs_erase_idempotent("test_nvs_key_asdf")
        main.nvs_erase_idempotent("test_nvs_key_asdf")
        val = main.nvs_get_default("test_nvs_key_asdf", 456)
        self.assertEqual(val, 456)

class TestCheckSchedule(unittest.TestCase):

    def test_no_task(self):
        check = main.CheckSchedule()
        tasks = check.runwith(
                itt=timeutil.parse_time("2020-08-27 07:29:00"),
                sched_cfg=[
                        ["TakeMeasurement", 'minutes', 30, 0],
                        ["Communicate", 'daily', 3, 15],
                    ])
        self.assertEqual(tasks, [])

    def test_have_task(self):

        check = main.CheckSchedule()
        tasks = check.runwith(
                itt=timeutil.parse_time("2020-08-27 07:30:05"),
                sched_cfg=[
                        ["TakeMeasurement", 'minutes', 30, 0],
                        ["Communicate", 'daily', 3, 15],
                    ])
        self.assertEqual(tasks, [main.TakeMeasurement])

    def test_bad_task(self):
        check = main.CheckSchedule()
        tasks = check.runwith(
                itt=timeutil.parse_time("2020-08-27 07:30:05"),
                sched_cfg=[
                        ["TakeMeasurement_X", 'minutes', 30, 0],
                        ["Communicate", 'daily', 3, 15],
                    ])
        self.assertEqual(tasks, [])

    def test_clock_drift_wake_early(self):
        check = main.CheckSchedule()
        tasks = check.runwith(
                itt=timeutil.parse_time("2020-08-27 07:30:05"),
                ett=timeutil.parse_time("2020-08-27 07:28:05"),
                sched_cfg=[
                        ["TakeMeasurement", 'minutes', 30, 0],
                        ["Communicate", 'daily', 3, 15],
                    ])
        # Don't schedule anything.
        # We will sync RTCs and wake up again on time
        self.assertEqual(tasks, [])

    def test_clock_drift_wake_late(self):
        check = main.CheckSchedule()
        tasks = check.runwith(
                itt=timeutil.parse_time("2020-08-27 07:30:05"),
                ett=timeutil.parse_time("2020-08-27 07:32:05"),
                sched_cfg=[
                        ["TakeMeasurement", 'minutes', 30, 0],
                        ["Communicate", 'daily', 3, 15],
                    ])
        # Do the task that we woke up for.
        # Otherwise it will never get done.
        self.assertEqual(tasks, [main.TakeMeasurement])

    def test_clock_drift_wake_barely_early(self):
        check = main.CheckSchedule()
        tasks = check.runwith(
                itt=timeutil.parse_time("2020-08-27 07:30:10"),
                ett=timeutil.parse_time("2020-08-27 07:30:05"),
                sched_cfg=[
                        ["TakeMeasurement", 'minutes', 30, 0],
                        ["Communicate", 'daily', 3, 15],
                    ])
        # Do the task that we woke up for.
        # Otherwise it will never get done.
        self.assertEqual(tasks, [main.TakeMeasurement])

    def test_clock_drift_reset_internal(self):
        check = main.CheckSchedule()
        tasks = check.runwith(
                itt=timeutil.parse_time("1970-01-01 00:30:10"),
                ett=timeutil.parse_time("2020-08-27 07:28:05"),
                sched_cfg=[
                        ["TakeMeasurement", 'minutes', 30, 0],
                        ["Communicate", 'daily', 3, 15],
                    ])
        # Do the task that we woke up for.
        # Otherwise it may never get done.
        self.assertEqual(tasks, [main.TakeMeasurement])

class TestSleepUntilScheduled(unittest.TestCase):

    def setUp(self):
        main.machine = mock_apis.MockMachine()
        main.sys = mock_apis.MockSys()
        main.hw = mock_apis.MockCo2UnitHw()
        main.utime = mock_apis.MockUtime()

    def test_sleep_until_next_task(self):
        sleep_until = main.SleepUntilScheduled()
        sleep_until.runwith(
                tt=timeutil.parse_time("2020-08-27 07:38:15"),
                sched_cfg=[
                        ["TakeMeasurement", 'minutes', 30, 0],
                        ["Communicate", 'daily', 3, 15],
                    ])

        self.assertTrue(main.hw._prepare_for_shutdown_called, True)
        self.assertTrue(main.machine._deepsleep_called)
        self.assertEqual(main.machine._deepsleep_time_ms, 1305000)

    def test_light_sleep_if_next_task_very_soon(self):
        sleep_until = main.SleepUntilScheduled()
        tasks = sleep_until.runwith(
                tt=timeutil.parse_time("2020-08-27 07:29:55"),
                sched_cfg=[
                        ["TakeMeasurement", 'minutes', 30, 0],
                        ["Communicate", 'daily', 3, 15],
                    ])

        # Deep sleep is not really worth it for less than ~30 sec.
        # Instead, light sleep and then go back to checking the schedule.
        # Be sure to put this step back in the queue again,
        # since we didn't deep sleep and reset the device.
        self.assertEqual(main.hw._prepare_for_shutdown_called, False)
        self.assertEqual(main.machine._deepsleep_called, False)
        self.assertEqual(main.utime._sleep_ms_called, True)
        self.assertEqual(main.utime._sleep_ms_time_ms, 5000)
        self.assertEqual(tasks, [main.CheckSchedule, main.SleepUntilScheduled])

    def test_sleep_if_hw_not_initialized(self):
        main.hw = None

        sleep_until = main.SleepUntilScheduled()
        sleep_until.runwith(
                tt=timeutil.parse_time("2020-08-27 07:38:15"),
                sched_cfg=[
                        ["TakeMeasurement", 'minutes', 30, 0],
                        ["Communicate", 'daily', 3, 15],
                    ])

class TestPersistentTaskLog(unittest.TestCase):

    class TaskA(object):
        def run(self): pass
    class TaskB(object):
        def run(self): pass
    class TaskC(object):
        def run(self): pass

    def setUp(self):
        main.machine = mock_apis.MockMachine()
        main.sys = mock_apis.MockSys()
        main.pycom = mock_apis.MockPycom()
        main.nvs_task_log = main.NvsTaskLog()

    def test_pack(self):
        ti = main.NvsTaskLog()
        ti.register(self.TaskA)

        event = (self.TaskA, "START", 1)

        packed = ti._pack_event(*event)
        self.assertIsInstance(packed, int)

        unpack = ti._unpack_event(packed)
        self.assertEqual(unpack, event)

    def test_pack_none(self):
        ti = main.NvsTaskLog()
        packed = ti._pack_event(None,None,0)
        self.assertEqual(ti._unpack_event(packed), (None, None, 0))
        self.assertEqual(ti._unpack_event(None), (None, None, 0))

    def test_pack_unregistered(self):
        ti = main.NvsTaskLog()
        packed = ti._pack_event(self.TaskA,None,0)
        self.assertEqual(ti._unpack_event(packed), ("UNKNOWN_TASK", None, 0))

    def test_unpack_unregistered(self):
        ti = main.NvsTaskLog()
        packed = ti.register(self.TaskA)
        packed = ti._pack_event(self.TaskA,None,0)
        ti = main.NvsTaskLog()
        self.assertEqual(ti._unpack_event(packed), (0, None, 0))

    def test_pack_too_many_reps(self):
        ti = main.NvsTaskLog()
        packed = ti._pack_event(None,None,257)
        self.assertEqual(ti._unpack_event(packed), (None, None, 255))

    def test_key_fmt(self):

        ti = main.NvsTaskLog()
        self.assertEqual(ti._key_str(20), "task_log_020")

    def test_record_start_ok_fail(self):

        ti = main.NvsTaskLog()
        ti.register(self.TaskA)

        self.assertEqual(ti.read_run_log(), [])

        ti.record_start(self.TaskA)
        self.assertEqual(ti.read_run_log(), [
            (self.TaskA,"START",1)])

        ti.record_ok(self.TaskA)
        self.assertEqual(ti.read_run_log(), [
            (self.TaskA,"START",1),
            (self.TaskA,"OK",1)])

        ti.record_fail(self.TaskA)
        self.assertEqual(ti.read_run_log(), [
            (self.TaskA,"START",1),
            (self.TaskA,"OK",1),
            (self.TaskA,"FAIL",1)])

    def test_record_repeated(self):

        ti = main.NvsTaskLog()
        ti.register(self.TaskA)

        self.assertEqual(ti.read_run_log(), [])

        ti.record_start(self.TaskA)
        self.assertEqual(ti.read_run_log(), [ (self.TaskA,"START",1)]) 

        ti.record_start(self.TaskA)
        self.assertEqual(ti.read_run_log(), [ (self.TaskA,"START",2) ])

    def test_log_limit(self):

        ti = main.NvsTaskLog()
        for i in range(0, ti.LOG_LEN):
            self.assertEqual(len(ti.read_run_log()), i)
            ti.register(i)
            ti.record_start(i)

        self.assertEqual(ti.read_run_log()[0], (0, "START", 1))
        self.assertEqual(ti.read_run_log()[-1], (ti.LOG_LEN-1, "START", 1))

        for i in range(ti.LOG_LEN, ti.LOG_LEN+5):
            self.assertEqual(len(ti.read_run_log()), ti.LOG_LEN)
            ti.register(i)
            ti.record_start(i)

        self.assertEqual(ti.read_run_log()[0], (5, "START", 1))
        self.assertEqual(ti.read_run_log()[-1], (ti.LOG_LEN+4, "START", 1))

        ti.reset_log()
        self.assertEqual(ti.read_run_log(), [])

    def test_persist_run_log(self):

        ti = main.NvsTaskLog()
        ti.register(self.TaskA)
        ti.register(self.TaskB)

        ti.record_start(self.TaskA)
        ti.record_start(self.TaskB)
        self.assertEqual(ti.read_run_log(), [
            (self.TaskA, "START", 1), (self.TaskB, "START", 1) ])

        # Create a fresh one
        ti = main.NvsTaskLog()
        ti.register(self.TaskA)
        ti.register(self.TaskB)

        # Should get previous values from NVS
        self.assertEqual(ti.read_run_log(), [
            (self.TaskA, "START", 1), (self.TaskB, "START", 1) ])

    def test_accept_unregistered(self):

        ti = main.NvsTaskLog()
        ti.register(self.TaskA)

        ti.record_start(self.TaskA)
        ti.record_start(self.TaskB)
        self.assertEqual(ti.read_run_log(), [
            (self.TaskA, "START", 1), ("UNKNOWN_TASK", "START", 1) ])

    def test_display_unregistered(self):

        ti = main.NvsTaskLog()
        ti.register(self.TaskA)
        ti.register(self.TaskB)
        ti.register(self.TaskC)

        ti.record_start(self.TaskA)
        ti.record_start(self.TaskB)
        ti.record_start(self.TaskC)
        self.assertEqual(ti.read_run_log(), [
            (self.TaskA, "START", 1),
            (self.TaskB, "START", 1),
            (self.TaskC, "START", 1),
            ])

        # Create a fresh one
        ti = main.NvsTaskLog()
        ti.register(self.TaskA)
        ti.register(self.TaskB)

        # Should get values from NVS, using just ids if not in registry
        self.assertEqual(ti.read_run_log(), [
            (self.TaskA, "START", 1),
            (self.TaskB, "START", 1),
            (2, "START", 1),
            ])

    def test_runner_tasks(self):

        class OkTask(object):
            def run(self): pass
        class FailTask(object):
            def run(self): raise Exception("Test Exception")

        main.nvs_task_log = main.NvsTaskLog()
        main.nvs_task_log.register(OkTask)
        main.nvs_task_log.register(FailTask)

        runner = main.TaskRunner()
        runner.run(OkTask, FailTask)

        self.assertEqual(main.nvs_task_log.read_run_log(), [
            (OkTask, "START", 1),
            (OkTask, "OK", 1),
            (FailTask, "START", 1),
            (FailTask, "FAIL", 1),
            ])
