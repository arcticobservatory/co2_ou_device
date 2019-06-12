import time

import logging

_logger = logging.getLogger("stopwatch")

class StopWatch(object):
    def __init__(self, name=None, logger=None):
        self.logger = logger or _logger
        self.start_ms(name)

    def start_ms(self, name=None, logstart=False):
        self.ticksfn = time.ticks_ms
        self.sleepfn = time.sleep_ms
        self.unit = "ms"
        self._start(name, logstart)

    def start_us(self, name=None, logstart=False):
        self.ticksfn = time.ticks_us
        self.sleepfn = time.sleep_us
        self.unit = "us"
        self._start(name, logstart)

    def _start(self, name, logstart):
        self.name = name
        self.start_ticks = self.ticksfn()
        if logstart and name:
            self.logger.debug("%s starting", name)

    def elapsed(self):
        return time.ticks_diff(self.start_ticks, self.ticksfn())

    def stop(self):
        elapsed = self.elapsed()
        if self.name: self.logger.debug("%s time: %d %s", self.name, elapsed, self.unit)
        return elapsed

    def wait_for(self, fn, timeout=10*1000, sleep=1):
        while True:
            result = fn()
            elapsed = self.elapsed()
            if result:
                if self.name: self.logger.debug("%s time: %d %s", self.name, elapsed, self.unit)
                return (result, elapsed)
            if elapsed > timeout:
                name = self.name or str(fn)
                msg = "Timeout waiting for %s after %d %s" % (name, elapsed, self.unit)
                self.logger.debug(msg)
                raise TimeoutError(msg)
            if sleep:
                self.sleepfn(sleep)
