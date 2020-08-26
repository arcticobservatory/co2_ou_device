
class MockSys(object):
    def __init__(self):
        self._exit_called = False

    def exit(self, exit_code=0):
        self._exit_called = True

class MockWdt(object):
    def __init__(self, timeout):
        self._init_count = 1
        self._init_timeout_ms = timeout
        self._feed_count = 0

    def init(self, timeout):
        self._init_count += 1
        self._init_timeout_ms = timeout

class MockMachine(object):
    def __init__(self):
        self._deepsleep_called = False
        self._deepsleep_time_ms = None
        self.WDT = MockWdt

    def deepsleep(self, time_ms):
        self._deepsleep_called = True
        self._deepsleep_time_ms = time_ms
