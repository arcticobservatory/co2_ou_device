import time

from onewire import OneWire
from onewire import DS18X20
from machine import Pin
from machine import UART

import logging

import stopwatch

_logger = logging.getLogger("ou_sensors")

class OuSensors(object):

    def __init__(self):
        _logger.debug("Initilizing external temperature sensor (onewire bus)")
        # # https://docs.pycom.io/tutorials/all/owd.html
        ow = OneWire(Pin('G15'))
        self.ext_temp = DS18X20(ow)

        _logger.debug("Initilizing flash pin (setting interrupt)")
        # # https://docs.pycom.io/firmwareapi/pycom/machine/pin.html
        self.flash_pin = Pin('P4', mode=Pin.IN, pull=Pin.PULL_UP)
        self.flash_pin.callback(Pin.IRQ_FALLING, self.on_flash_pin)

        _logger.debug("Initializing CO2 sensor")
        self.co2 = ExplorIR(scale=10)
        self.co2.set_mode(EXPLORIR_MODE_POLLING)

    def take_reading(self):
        rtime = time.gmtime()

        timer = stopwatch.StopWatch(logger=_logger)
        timer.start_ms("Sensor reading", logstart=True)

        # Start temperature reading
        self.ext_temp.start_conversion()

        co2 = self.co2.read_co2()

        # Wait for temperature reading
        # Temperature reading seems to take around 650 ms (datasheet says under 750 ms)
        ext_t, ext_t_ms = timer.wait_for(
                self.ext_temp.read_temp_async,
                timeout=2000, sleep=1);

        # Read flash sensor
        flash_reading = self.flash_pin()

        reading = {
                "rtime": rtime,
                "co2": co2,
                "ext_t": ext_t,
                "ext_t_ms": ext_t_ms,
                "flash": flash_reading,
                }
        return reading

    def on_flash_pin(self, *args):
        print("pin change", *args)

EXPLORIR_MODE_CMD = const(0)
EXPLORIR_MODE_STREAMING = const(1)
EXPLORIR_MODE_POLLING = const(2)

class ExplorIR(object):
    def __init__(self, scale=10):
        self.uart = UART(1, 9600)
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
