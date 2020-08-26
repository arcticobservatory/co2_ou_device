import logging
_logger = logging.getLogger("mock_apis")

class MockSys(object):
    def __init__(self):
        self._exit_called = False

    def exit(self, exit_code=0):
        _logger.info("sys.exit(%s)", exit_code)
        self._exit_called = True

class MockWdt(object):
    def __init__(self, timeout):
        self._init_count = 1
        self._init_timeout_ms = timeout
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

class MockPycom(object):

    def __init__(self):
        self._nvram = {}

    def nvs_get(self, key):
        try:
            return self._nvram[key]
        except KeyError as e:
            # The actual Pycom API raises a ValueError on nonexistent key
            raise ValueError(e)

    def nvs_set(self, key, val):
        _logger.info("pycom.nvs_set(%s, %s)", key, val)
        self._nvram[key] = val

    def nvs_erase(self, key):
        del(self._nvram[key])
