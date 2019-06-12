from machine import UART
import logging
import stopwatch

EXPLORIR_MODE_CMD = const(0)
EXPLORIR_MODE_STREAMING = const(1)
EXPLORIR_MODE_POLLING = const(2)

_logger = logging.getLogger("explorir")

class ExplorIR(object):
    def __init__(self, uart=1, scale=10):
        self.uart = UART(uart, 9600)
        self.scale = scale

    def set_mode(self, mode):
        cmd = b"K %d\r\n" % mode
        _logger.debug("CO2: switching to mode %d" % mode)
        _logger.debug("CO2 < %s", cmd)
        self.uart.write(cmd)
        def command_ack():
            line = self.uart.readline()
            _logger.debug("CO2 > %s", line)
            if line == None:
                return None
            line = line.decode("ascii")
            if line.startswith(" K "):
                K = int(line[3:8])
                if K!=mode:
                    raise Exception("CO2 responded with unexpected mode: %s" % line)
                return line
            elif line.startswith(" ?"):
                raise Exception("Error CO2 sensor response: %s" % line)
            else:
                return None
        timer = stopwatch.StopWatch("CO2 sensor poll mode ack")
        timer.wait_for(command_ack, timeout=100, sleep=1)

    def read_co2(self):
        cmd = b"Z\r\n"
        _logger.debug("CO2: reading")
        _logger.debug("CO2 < %s", cmd)
        self.uart.write(cmd)
        timer = stopwatch.StopWatch("CO2 sensor read")
        line, _ = timer.wait_for(self.uart.readline, timeout=100, sleep=1)
        _logger.debug("CO2 > %s", line)
        line = line.decode("ascii")
        if not line.startswith(" Z "):
            raise Exception("Unexpected CO2 sensor response: %s" % line)
        Z = int(line[3:8])
        ppm = Z * self.scale
        return ppm
