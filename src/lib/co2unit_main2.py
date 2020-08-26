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

    def __init__(self, wdt):
        self.queue = []
        self.history = []
        self.wdt = wdt

    def run_next_task(self):
        task = self.queue[0]
        self.queue = self.queue[1:]

        instance = task() if isinstance(task, type) else task
        try:
            instance.run(wdt=self.wdt)
            self.history.append( (instance, None) )
        except KeyboardInterrupt:
            raise
        except:
            _logger.exception("Task %s failed", instance)
            exc_type, exc_val, _ = sys.exc_info()
            self.history.append( (instance, exc_val) )

    def run(self, *tasks):
        self.queue += tasks
        while self.queue:
            self.wdt.feed()
            self.run_next_task()
