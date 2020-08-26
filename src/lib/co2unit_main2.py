import sys

try:
    import machine
except:
    import mock_apis
    machine = mock_apis.MockMachine()

import logging
_logger = logging.getLogger("main")
_logger.setLevel(logging.DEBUG)

RUNNING_WDT_MS = 1000*60*2
REPL_WDT_MS = 1000*60*60*24
LAST_RESORT_DEEPSLEEP_MS = 1000*60*15

class MainWrapper(object):
    """ Top-level run behavior

    - Suppress exceptions (except KeyboardInterrupt) so that unhandled errors
      do not cause exit to REPL
    - Instead, go into deep sleep for a specified amount of time as a last resort
    - Initialize watchdog timer (extend on KeyboardInterrupt exit to REPL)
    """
    def __init__(self, machine_api=machine, sys_api=sys):
        self.machine_api = machine_api
        self.sys_api = sys_api
        self.wdt = None

    def __enter__(self):
        _logger.info("Entering MainWrapper. Initializing WDT (%d ms)", RUNNING_WDT_MS)
        self.wdt = self.machine_api.WDT(RUNNING_WDT_MS)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type == KeyboardInterrupt:
            _logger.info("KeyboardInterrupt detected. Extending WDT (%d ms) and exiting to REPL.", REPL_WDT_MS)
            self.wdt.init(REPL_WDT_MS)
            self.sys_api.exit()
            return False

        if exc_val:
            _logger.exc(exc_val, "Uncaught exception at MainWrapper top level")

        _logger.warning("Control got to MainWrapper last resort. Don't know what else to do. Going to sleep for a while (%d ms).", LAST_RESORT_DEEPSLEEP_MS)
        self.machine_api.deepsleep(LAST_RESORT_DEEPSLEEP_MS)
        return False

class TaskRunner(object):

    def __init__(self):
        self.queue = []
        self.history = []

    def push_task(self, task):
        pass

    def _run_one(self):
        pass

    def run(self):
        pass

class NvState(object):
    nv_main_keys = []

    def __init__(self, pycom_api):
        self.pycom = pycom_api
        self.vals = {}
        for name in nv_main_keys:
            self.__getattr__(name)

    def __getattr__(self, name):
        self.vals[name] = self.pycom.nvs_get(name)
        return self.vals[name]

    def __setattr__(self, name, value):
        retval = self.pycom.nvs_set(name, value)
        self.vals[name] = value
        return retval

    def __delattr__(self, name):
        retval = self.pycom.nvs_erase(name)
        del(self.vals[name])
        return retval

    def __str__(self):
        return str(self.vals)

class RunStep(object):
    deps = []
    def run(self):
        pass

class RunReactor(object):

    def __init__(self):
        self.queue = []
        self.history = []
        self.failed = set()

    def push_step(self, *steps):
        for step in steps:
            assert issubclass(step, RunStep)
        self.queue = list(steps) + self.queue
        self._resolve_deps()

    def _resolve_deps(self):
        resolved = []
        seen = set()
        stack = list(reversed(self.queue))
        while stack:
            _logger.debug("Resolving deps. Resolved: %s; Stack: %s", resolved, stack)
            cur = stack.pop()
            seen.add(cur)
            new_deps = [dep for dep in cur.deps
                    if dep not in resolved \
                            and dep not in self.history]
            if new_deps:
                seen_deps = [dep for dep in new_deps if dep in seen]
                if seen_deps:
                    assert False, "circular RunStep dependency: %s -> %s" % (cur, seen_deps)
                stack.append(cur)
                stack.extend(reversed(new_deps))
            else:
                resolved.append(cur)
        self.queue = resolved

    def run_next(self):
        step = self.queue[0]
        self.queue = self.queue[1:]
        self._run_step(step)

    def _run_step(self, step):
        assert issubclass(step, RunStep)
        self.history.append(step)
        _logger.info("Step %s starting. Then: %s", step, self.queue)

        new_steps = []
        try:
            new_steps = step().run()
            _logger.info("Step %s OK. New requests: %s.", step, new_steps)
        except KeyboardInterrupt:
            raise
        except:
            self.failed.add(step)
            _logger.exception("Uncaught Exception during step %s", step)
            pass

        if new_steps:
            self.push_step(*new_steps)
        _logger.info("Step %s starting. Then: %s", step, self.queue)
