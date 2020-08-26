import sys

import unittest
import logging

import mock_apis

from co2unit_main2 import *

# Suppress logging
_logger = logging.getLogger("main")
_logger.setLevel(logging.CRITICAL)
_logger.exception = lambda *args: None
_logger.exc = lambda *args: None

logging.getLogger("mock_apis").setLevel(logging.CRITICAL)

class TestMainWrapper(unittest.TestCase):

    def test_normal_exit(self):
        mock_machine = mock_apis.MockMachine()
        mock_sys = mock_apis.MockSys()
        with MainWrapper(machine_api=mock_machine, sys_api=mock_sys):
            pass
        self.assertTrue(mock_machine._deepsleep_called)
        self.assertEqual(mock_machine._deepsleep_time_ms, LAST_RESORT_DEEPSLEEP_MS)

    def test_exception_exit(self):
        mock_machine = mock_apis.MockMachine()
        mock_sys = mock_apis.MockSys()
        class TestException(Exception):
            pass
        with self.assertRaises(TestException):
            with MainWrapper(machine_api=mock_machine, sys_api=mock_sys):
                raise TestException()
        self.assertTrue(mock_machine._deepsleep_called)
        self.assertEqual(mock_machine._deepsleep_time_ms, LAST_RESORT_DEEPSLEEP_MS)

    def test_keyboard_interrupt(self):
        mock_machine = mock_apis.MockMachine()
        mock_sys = mock_apis.MockSys()
        with self.assertRaises(KeyboardInterrupt):
            with MainWrapper(machine_api=mock_machine, sys_api=mock_sys):
                raise KeyboardInterrupt()
        self.assertFalse(mock_machine._deepsleep_called)
        self.assertTrue(mock_sys._exit_called)

    def test_wdt_control(self):
        mock_machine = mock_apis.MockMachine()
        mock_sys = mock_apis.MockSys()

        with self.assertRaises(KeyboardInterrupt):
            with MainWrapper(machine_api=mock_machine, sys_api=mock_sys) as main:
                self.assertEqual(main.wdt._init_count, 1)
                self.assertEqual(main.wdt._init_timeout_ms, RUNNING_WDT_MS)
                raise KeyboardInterrupt()

        self.assertEqual(main.wdt._init_count, 2)
        self.assertEqual(main.wdt._init_timeout_ms, REPL_WDT_MS)


class TestTaskRunner(unittest.TestCase):

    def test_run_task(self):
        class MockTask(object):
            def __init__(self): self._was_run = False
            def run(self, **kwargs): self._was_run = True

        task = MockTask()

        runner = TaskRunner(mock_apis.MockWdt(0))
        runner.run(task)
        self.assertTrue(task._was_run)
        self.assertNotEqual(runner.wdt._feed_count, 0, "WDT should have been fed")

    def test_accept_task_class(self):
        side_effect = {"was_run": False}
        class TaskClass(object):
            def run(self, **kwargs):
                side_effect["was_run"] = True

        runner = TaskRunner(mock_apis.MockWdt(0))
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

        runner = TaskRunner(mock_apis.MockWdt(0))
        try:
            runner.run(task)
        except MockException:
            self.fail("MockException was allowed to pass through")
        self.assertEqual(runner.history, [(task, exc_val)])

        class KeyboardTask(object):
            def run(self, **kwargs):
                raise KeyboardInterrupt()

        with self.assertRaises(KeyboardInterrupt):
            runner.run(KeyboardTask)
