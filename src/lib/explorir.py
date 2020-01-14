from machine import UART
import logging
import time

EXPLORIR_MODE_CMD = const(0)
EXPLORIR_MODE_STREAMING = const(1)
EXPLORIR_MODE_POLLING = const(2)

_logger = logging.getLogger("explorir")
_logger.setLevel(logging.DEBUG)

class ExplorIrError(Exception): pass

class ExplorIr(object):
    def __init__(self, uart):
        self.uart = uart
        self._multiplier = None

    def uart_read_lines(self, expect_output=True, timeout_ms=200, read_wait_ms=1):
        """ Read from the UART buffer until there is nothing left to read

            Returns an array of lines read, decoded from ascii
        """

        start_ticks = time.ticks_ms()
        lines = []
        output_started = False

        while True:

            line = self.uart.readline()
            _logger.debug("UART > %s", line)

            if line != None:
                line = line.decode("ascii")
                lines.append(line)
                output_started = True

            elif expect_output and not output_started:
                elapsed = time.ticks_diff(start_ticks, time.ticks_ms())
                if elapsed > timeout_ms:
                    raise TimeoutError("Timeout waiting for output: %d ms" % elapsed)
                time.sleep_ms(read_wait_ms)

            else:
                # Either not waiting for output, or output started and finished
                break

        return lines


    def uart_cmd(self, cmd, expect_lines=1, expect_code=None, timeout_ms=200, read_wait_ms=1):
        """ Sends a command over the UART interface

            Returns array of response lines (if any)
        """
        # Flush previous output if any
        flush = self.uart_read_lines(expect_output=False, timeout_ms=timeout_ms, read_wait_ms=read_wait_ms)
        if flush:
            _logger.warning("Discarding earlier buffered output: %s", flush)

        # Send command
        _logger.debug("UART < %s", cmd)
        self.uart.write(cmd)

        # Read output
        lines = self.uart_read_lines(expect_output=bool(expect_lines), timeout_ms=timeout_ms, read_wait_ms=read_wait_ms)

        # Check output
        if expect_lines and len(lines) != expect_lines:
            raise ExplorIrError("Unexpected output after cmd %s. Expected %s lines, got %s: %s" %
                    (cmd, expect_lines, len(lines), lines))

        elif expect_code and not lines:
            raise ExplorIrError("Unexpected output after cmd %s. Expected %s response, got no output" %
                    (cmd, expect_code))

        elif expect_code and lines[0][1] != expect_code:
            raise ExplorIrError("Unexpected output after cmd %s. Expected %s response, got %s" %
                    (cmd, expect_code, lines))

        elif lines and lines[0][1] == '?' and expect_code != '?':
            raise ExplorIrError("Error output after cmd %s: %s" %
                    (cmd, lines))

        else:
            return lines

    def uart_cmd_return_int(self, cmd, expect_code=None, timeout_ms=200, read_wait_ms=1):
        line = self.uart_cmd(cmd, expect_lines=1, expect_code=expect_code, timeout_ms=timeout_ms, read_wait_ms=read_wait_ms)[0]
        try:
            val = int(line[3:8])
            return val
        except ValueError as e:
            raise ExplorIrError("Unexpected output after cmd %s. Expected response with integer value, got %s." %
                    (cmd, lines))

    def read_multiplier(self):
        _logger.debug("Reading CO2 multiplier for sensor")
        cmd = b".\r\n"
        val = self.uart_cmd_return_int(cmd, expect_code=".")
        return val

    @property
    def multiplier(self):
        if not self._multiplier:
            self._multiplier = self.read_multiplier()
        return self._multiplier

    def set_mode(self, mode):
        _logger.debug("Switching to mode %d" % mode)
        cmd = b"K %d\r\n" % mode
        val = self.uart_cmd_return_int(cmd, expect_code="K")
        if val!=mode:
            raise ExplorIrError("Switch to mode %d failed. Got response mode %s" % (mode, val))

    def read_co2(self):
        _logger.debug("Reading CO2 value")
        cmd = b"Z\r\n"
        val = self.uart_cmd_return_int(cmd, expect_code="Z")
        ppm = val * self.multiplier
        return ppm
