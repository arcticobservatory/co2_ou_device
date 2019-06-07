import time

import logging

_logger = logging.getLogger("polling")

_ticks_fns = {
        "ms": time.ticks_ms,
        "us": time.ticks_us,
        }

_sleep_fns = {
        "ms": time.sleep_ms,
        "us": time.sleep_us,
        }

class PollTimeout(Exception): pass

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
            self.sleepfn(sleep)

def time_fn_us(fn, *args, **kwargs):
    start = time.ticks_us()
    result = fn(*args, **kwargs)
    elapsed = time.ticks_diff(start, time.ticks_us())
    _logger.debug("%s time: %d us", str(fn), elapsed)
    return (result, elapsed)

def poll_wait_ms(poll_fn, timeout_ms=1000, sleep_ms=1):
    start_ticks = time.ticks_ms()
    while True:
        result = poll_fn()
        ticks = time.ticks_diff(start_ticks, time.ticks_ms())
        if result:
            return (result, ticks)
        if ticks > timeout_ms:
            raise TimeoutError("Timeout after {} ms".format(ticks))
        time.sleep_ms(sleep_ms)

def poll_sleep_loop(poll_fns_dict, ticks_unit="ms", timeout_ticks=1000, sleep_ticks=10):

    ticks_fn = _ticks_fns[ticks_unit]
    sleep_fn = _sleep_fns[ticks_unit]

    start_ticks = ticks_fn()

    results = {k: None for k, _ in poll_fns_dict.items()}

    _logger.debug("Entering poll loop for %s", poll_fns_dict.keys())
    _logger.debug("Timeout after %d %s, each sleep %d %s",
                timeout_ticks, ticks_unit, sleep_ticks, ticks_unit)
    while True:
        for k, fn in poll_fns_dict.items():
            if not results[k]:
                result = fn()
                if result:
                    ticks = time.ticks_diff(start_ticks, ticks_fn())
                    _logger.debug("%s returned after %d %s: %s", k, ticks, ticks_unit, result)
                    results[k] = (result, ticks)

        if all(results.values()):
            _logger.debug("All completed: %s", poll_fns_dict.keys())
            return results

        if time.ticks_diff(start_ticks, ticks_fn()) > timeout_ticks:
            msg = "Timeout reached (%d %s) waiting for %s" % \
                    (timeout_ticks, ticks_unit, poll_fns_dict.keys())
            _logger.debug(msg)
            raise PollTimeout(msg)

        sleep_fn(sleep_ticks)
