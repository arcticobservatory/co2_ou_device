import logging
_logger = logging.getLogger("mock_apis")

import sys as real_sys

class MockSys(object):
    def __init__(self):
        self._exit_called = False

    def exit(self, exit_code=0):
        _logger.info("sys.exit(%s)", exit_code)
        self._exit_called = True

    def exc_info(self):
        return real_sys.exc_info()

class MockWdt(object):
    def __init__(self, id=0, timeout=None):
        self._init_count = 1
        self._init_timeout_ms = int(timeout)
        self._feed_count = 0

    def init(self, timeout):
        self._init_count += 1
        self._init_timeout_ms = timeout

    def feed(self):
        self._feed_count += 1

class MockMachine(object):
    def __init__(self):
        self._deepsleep_called = False
        self._deepsleep_time_ms = None
        self.WDT = MockWdt

    def deepsleep(self, time_ms):
        _logger.info("machine.deepsleep(%s)", time_ms)
        self._deepsleep_called = True
        self._deepsleep_time_ms = time_ms

# Some versions throw ValueError, others simply return None
PYCOM_EXCEPTION_ON_NONEXISTENT_KEY = None
#PYCOM_EXCEPTION_ON_NONEXISTENT_KEY = ValueError

class MockPycom(object):

    def __init__(self):
        self._nvram = {}

    def nvs_get(self, key):
        if key in self._nvram:
            return self._nvram[key]
        elif PYCOM_EXCEPTION_ON_NONEXISTENT_KEY:
            raise PYCOM_EXCEPTION_ON_NONEXISTENT_KEY()
        else:
            return None

    def nvs_set(self, key, val):
        _logger.info("pycom.nvs_set(%s, %s)", key, val)
        self._nvram[key] = val

    def nvs_erase(self, key):
        del(self._nvram[key])


class MockCo2UnitHw(object):
    def __init__(self):
        self._prepare_for_shutdown_called = False

    def prepare_for_shutdown(self):
        self._prepare_for_shutdown_called = True
