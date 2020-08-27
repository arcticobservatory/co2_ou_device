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

class TestSleepUntilScheduled(unittest.TestCase):

    def setUp(self):
        main.machine = mock_apis.MockMachine()
        main.sys = mock_apis.MockSys()
        main.hw = mock_apis.MockCo2UnitHw()

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
