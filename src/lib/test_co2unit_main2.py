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

class TestReactor(unittest.TestCase):

    def test_run_step(self):
        side_effect = {"was_run": False}
        class DummyStep(RunStep):
            def run(self):
                side_effect['was_run'] = True

        reactor = RunReactor()
        reactor._run_step(DummyStep)
        self.assertTrue(side_effect['was_run'],
                "Run method should have been called")

    def test_run_step_error(self):
        class TestException(Exception): pass
        class ThrowStep(RunStep):
            def run(self):
                raise TestException("Whoopsie!")

        reactor = RunReactor()
        try:
            reactor._run_step(ThrowStep)
        except TestException as e:
            self.fail("Run procedure should not allow exceptions to escape. Raised %s: %s" % (type(e).__name__, e))

        class KeyboardStep(RunStep):
            def run(self):
                raise KeyboardInterrupt()

        with self.assertRaises(KeyboardInterrupt):
            reactor._run_step(KeyboardStep)

    def test_resolve(self):
        class A(RunStep): pass
        class B(RunStep): deps = [A]
        class C(RunStep): deps = [A,B]

        reactor = RunReactor()
        reactor.push_step(C)
        self.assertEqual(reactor.queue, [A,B,C])

    def test_resolve_circular(self):
        class A(RunStep): pass
        class B(RunStep): deps = [A]
        class C(RunStep): deps = [A,B]

        A.deps = [B]

        reactor = RunReactor()

        with self.assertRaises(AssertionError):
            reactor.push_step(C)

    def test_record_run(self):
        class OkStep(RunStep): pass

        reactor = RunReactor()
        reactor.push_step(OkStep)
        reactor.run_next()
        self.assertEqual(reactor.history, [OkStep])

    def test_record_fail(self):
        class FailStep(RunStep):
            def run(self):
                raise Exception("this step always fails")

        reactor = RunReactor()
        reactor.push_step(FailStep)
        reactor.run_next()
        self.assertEqual(reactor.history, [FailStep])
        self.assertIn(FailStep, reactor.failed)

    def test_step_can_queue(self):
        class A(RunStep):
            def run(self):
                return [B]
        class B(RunStep): pass

        reactor = RunReactor()
        reactor.push_step(A)
        reactor.run_next()
        self.assertEqual(reactor.queue, [B])
