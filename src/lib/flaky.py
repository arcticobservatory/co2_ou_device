import time

import logging

_logger = logging.getLogger("flaky")

def retry_call(fn, *args, attempts=5, wait_ms=None, **kwargs):
    name = str(fn)
    for i in range(1, attempts+1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            _logger.warning("%s failed (attempt %d of %d) with %s: %s",
                    name, i, attempts, type(e).__name__, e)
            if i == attempts:
                raise
            if wait_ms:
                time.sleep_ms(wait_ms)
