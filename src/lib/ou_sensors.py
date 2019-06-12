import time

from onewire import OneWire
from onewire import DS18X20
from machine import Pin

import logging

import stopwatch
import explorir

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
        self.co2 = explorir.ExplorIR(uart=1, scale=10)
        self.co2.set_mode(explorir.EXPLORIR_MODE_POLLING)

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
