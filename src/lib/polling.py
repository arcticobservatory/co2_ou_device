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

def poll_sleep_loop(poll_fns_dict, ticks_unit="ms", timeout_ticks=1000, sleep_ticks="10"):

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
            _logger.debug("Timeout reached (%d %s) waiting for %s",
                    timeout_ticks, ticks_unit, poll_fns_dict.keys())
            raise PollTimeout()

        sleep_fn(sleep_ticks)
