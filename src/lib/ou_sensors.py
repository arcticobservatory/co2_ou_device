import time

from onewire import OneWire
from onewire import DS18X20
from machine import Pin
import logging

_logger = logging.getLogger("ou_sensors")

class OuSensors(object):

    def __init__(self):
        _logger.debug("Initilizing external temperature sensor (onewire bus)")
        # # https://docs.pycom.io/tutorials/all/owd.html
        ow = OneWire(Pin('P3'))
        self.ext_temp = DS18X20(ow)

        _logger.debug("Initilizing flash pin (setting interrupt)")
        # # https://docs.pycom.io/firmwareapi/pycom/machine/pin.html
        self.flash_pin = Pin('P4', mode=Pin.IN, pull=Pin.PULL_UP)
        self.flash_pin.callback(Pin.IRQ_FALLING, self.on_flash_pin)

    def take_reading(self):

        _logger.debug("Starting temperature reading")
        # Start temperature reading
        self.ext_temp.start_conversion()
        ext_t_start_ticks = time.ticks_ms()

        # Wait for temperature reading
        # Temperature reading seems to take around 650 ms (datasheet says under 750 ms)
        while True:
            ext_t_reading = self.ext_temp.read_temp_async()
            if ext_t_reading != None:
                ext_t_ticks = time.ticks_diff(ext_t_start_ticks, time.ticks_ms())
                _logger.debug("Temperature reading %s C; completed in %d ms",
                            ext_t_reading, ext_t_ticks)
                break
            time.sleep_ms(1)

        # Read flash sensor
        flash_reading = self.flash_pin()

        reading = {
                "co2": None,
                "ext_t": ext_t_reading,
                "ext_t_ms": ext_t_ticks,
                "flash": flash_reading,
                }
        return reading

    def on_flash_pin(self, *args):
        print("pin change", *args)
