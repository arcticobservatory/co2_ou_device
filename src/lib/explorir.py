from machine import UART
import logging
import time

EXPLORIR_MODE_CMD = const(0)
EXPLORIR_MODE_STREAMING = const(1)
EXPLORIR_MODE_POLLING = const(2)

_logger = logging.getLogger("explorir")

class ExplorIrError(Exception): pass

class ExplorIr(object):
    def __init__(self, uart, scale=10):
        self.uart = uart
        self.scale = scale

    def uart_cmd(self, cmd, expect_code=None, skip_others=False, timeout_ms=100):
        _logger.debug("UART < %s", cmd)
        self.uart.write(cmd)

        start_ticks = time.ticks_ms()
        while True:
            line = self.uart.readline()
            _logger.debug("UART > %s", line)
            if line == None:
                # No answer yet. Wait and try again
                time.sleep_ms(1)
            else:
                line = line.decode("ascii")
                if line[1]==expect_code:
                    return line
                elif line[1]=="?":
                    raise ExplorIrError("Error response from CO2 sensor: %s" % line)
                elif not skip_others:
                    raise ExplorIrError("Unexpected response from CO2 sensor: %s" % line)

            elapsed = time.ticks_diff(start_ticks, time.ticks_ms())
            if elapsed > timeout_ms:
                raise TimeoutError("Timeout trying to read CO2 sensor: %d ms" % elapsed)

    def set_mode(self, mode):
        _logger.debug("CO2: switching to mode %d" % mode)
        cmd = b"K %d\r\n" % mode
        line = self.uart_cmd(cmd, expect_code="K", skip_others=True)
        K = int(line[3:8])
        if K!=mode:
            raise ExplorIrError("Switch to mode %d failed. Got response %s" % (mode, line))

    def read_co2(self):
        _logger.debug("CO2: reading")
        cmd = b"Z\r\n"
        line = self.uart_cmd(cmd, expect_code="Z")
        Z = int(line[3:8])
        ppm = Z * self.scale
        return ppm
