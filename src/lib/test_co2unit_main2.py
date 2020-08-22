import unittest
import logging
from co2unit_main2 import *

_logger = logging.getLogger("reactor")
#_logger.setLevel(logging.CRITICAL)
#_logger.exception = lambda *args: None

class TestContextManater(unittest.TestCase):

    def test_binding_context_manager(self):

        class TrialManager(object):
            def __init__(self, param):
                self.param = param

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                return False

        with TrialManager("passed-in string") as bound:
            self.assertEqual(bound.param, "passed-in string")

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
