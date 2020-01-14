from machine import UART
import logging
import time

_logger = logging.getLogger("explorir")
_logger.setLevel(logging.DEBUG)

TIMEOUT_MS=200
READ_WAIT_MS=10

MODE_CMD = const(0)
MODE_STREAMING = const(1)
MODE_POLLING = const(2)

FIELD_HUMIDITY = 'H'
FIELD_LED_NORMALIZED_FILTERED = 'd'
FIELD_LED_NORMALIZED_UNFILTERED = 'D'
FIELD_ZERO_POINT = 'h'
FIELD_SENSOR_TEMPERATURE_UNFILTERED = 'V'
FIELD_TEMPERATURE = 'T'
FIELD_LED_SIGNAL_FILTERED = 'o'
FIELD_LED_SIGNAL_UNFILTERED = 'O'
FIELD_SENSOR_TEMPERATURE_FILTERED = 'v'
FIELD_CO2_OUTPUT_FILTERED = 'Z'
FIELD_CO2_OUTPUT_UNFILTERED = 'z'

FIELD_MASKS = {
    FIELD_HUMIDITY: 4096,
    FIELD_LED_NORMALIZED_FILTERED: 2048,
    FIELD_LED_NORMALIZED_UNFILTERED: 1024,
    FIELD_ZERO_POINT: 256,
    FIELD_SENSOR_TEMPERATURE_UNFILTERED: 128,
    FIELD_TEMPERATURE: 64,
    FIELD_LED_SIGNAL_FILTERED: 32,
    FIELD_LED_SIGNAL_UNFILTERED: 16,
    FIELD_SENSOR_TEMPERATURE_FILTERED: 8,
    FIELD_CO2_OUTPUT_FILTERED: 4,
    FIELD_CO2_OUTPUT_UNFILTERED: 2,
}

MULTI_FIELD_MAX = 5

class ExplorIrError(Exception): pass

class ExplorIr(object):
    def __init__(self, uart):
        self.uart = uart
        self._multiplier = None

    def uart_read_lines(self, expect_output=True):
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
                if elapsed > TIMEOUT_MS:
                    raise TimeoutError("Timeout waiting for output: %d ms" % elapsed)
                time.sleep_ms(READ_WAIT_MS)

            else:
                # Either not waiting for output, or output started and finished
                break

        return lines


    def uart_cmd(self, cmd, expect_lines=1, expect_code=None):
        """ Sends a command over the UART interface

            Returns array of response lines (if any)
        """
        # Flush previous output if any
        flush = self.uart_read_lines(expect_output=False)
        if flush:
            _logger.warning("Discarding earlier buffered output: %s", flush)

        # Send command
        _logger.debug("UART < %s", cmd)
        self.uart.write(cmd)

        # Read output
        lines = self.uart_read_lines(expect_output=bool(expect_lines))

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

    def uart_cmd_return_int(self, cmd, expect_code=None, expect_int=None):
        line = self.uart_cmd(cmd, expect_lines=1, expect_code=expect_code)[0]
        try:
            val = int(line[3:8])
        except ValueError as e:
            raise ExplorIrError("Unexpected output after cmd %s. Expected response with integer value, got %r" %
                    (cmd, line))

        if expect_int and val != expect_int:
            raise ExplorIrError("Unexpected output after cmd %s. Expected response with value %s, got %r" %
                    (cmd, expect_int, line))

        return val

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
        self.uart_cmd_return_int(cmd, expect_code="K", expect_int=mode)

    def read_co2(self):
        _logger.debug("Reading CO2 value")
        cmd = b"Z\r\n"
        val = self.uart_cmd_return_int(cmd, expect_code="Z")
        ppm = val * self.multiplier
        return ppm

    def select_fields(self, fields):
        """ Select fields (M) for multi-field output (Q)

            fields parameter can be an array of field codes or a string.
            Examples:
                ['d','h','v','o','Z']
                'dhvoZ'

            See the FIELD_* constants
        """
        if len(fields) > MULTI_FIELD_MAX:
            raise ExplorIrError("Asked to select %s fields. Max is %s. Input: %s" %
                    (len(fields), MULTI_FIELD_MAX, fields))

        masks = 0
        for field in fields:
            try:
                mask = FIELD_MASKS[field]
                masks += mask
            except KeyError:
                raise ExplorIrError("Unexpected field %s. Unknown mask for %s." %
                        (field,field))

        cmd = b"M %d\r\n" % masks
        self.uart_cmd_return_int(cmd, expect_code="M", expect_int=masks)

    def read_fields(self):
        _logger.debug("Reading multi-fields")
        cmd = b"Q\r\n"
        line = self.uart_cmd(cmd, expect_lines=1)[0]
        _logger.debug("Response line: %r", line)

        # Convert values line to dictionary
        #
        # Output line will look something like this:
        # ' d 32274 h 32989 o 31179 v 18373 Z 00229\r\n'
        #
        # Each field is 8 chars: space, field, space, five digits.
        # Line is terminated by '\r\n'
        #
        # Want to parse as {'d':32247, 'h':32989, ...}

        vals = {}
        pos = 0
        while pos + 8 < len(line) and line[pos]!='\r':
            field = line[pos+1]
            val = line[pos+3:pos+8]
            try:
                val = int(val)
            except ValueError:
                raise ExplorIrError("Q command: Could not parse %r as field with int value. Response line: %r" %
                        (line[pos:pos+8], line))
            vals[field] = val
            pos += 8

        _logger.debug("Parsed line: %s", vals)
        return vals
