import logging

from machine import Pin
from machine import SPI
from machine import UART

from ds3231 import DS3231
from onewire import DS18X20
from onewire import OneWire
import explorir
import sdcard

_logger = logging.getLogger("co2unit_hw")

class NoSdCardError(Exception): pass

class Co2UnitHw(object):
    def __init__(self):
        self._co2 = None
        self._etemp = None
        self._ertc = None
        self._sdcard = None
        self._select_production_pins()

    def _select_production_pins(self):
        _logger.debug("Selecting pins for production unit")
        self._co2_uart = UART(1, 9600)
        self._i2c_pins = ('P22', 'P21')

        self._onewire_pin = Pin('P23')
        self._sd_cs = Pin('P9')
        self._flash_pin = Pin('P2')
        self._mosfet_pin = Pin('P12')

    def _select_breadboard_pins(self):
        _logger.debug("Selecting pins for breadboard unit")
        self._co2_uart = UART(1, 9600)
        self._i2c_pins = ('P22', 'P21')

        self._onewire_pin = Pin('G15')
        self._sd_cs = Pin('P12')
        self._flash_pin = Pin('P4')
        self._mosfet_pin = None

    def mosfet_pin(self):
        return self._mosfet_pin

    def sdcard(self):
        if not self._sdcard:
            _logger.debug("Initializing SD card")
            self._spi = SPI(0, mode=SPI.MASTER)
            try:
                self._sdcard = sdcard.SDCard(self._spi, self._sd_cs)
            except OSError as e:
                if "no sd card" in str(e).lower():
                    raise NoSdCardError(e)
                else:
                    raise
        return self._sdcard

    def ertc(self):
        if not self._ertc:
            _logger.debug("Initializing external RTC")
            self._ertc = DS3231(0, pins=self._i2c_pins)
        return self._ertc

    def flash_pin(self):
        return self._flash_pin

    def co2(self):
        if not self._co2:
            _logger.debug("Initializing co2 sensor")
            self._co2 = explorir.ExplorIr(self._co2_uart, scale=10)
        return self._co2

    def etemp(self):
        if not self._etemp:
            _logger.debug("Initializing external temp sensor")
            onewire_bus = OneWire(self._onewire_pin)
            self._etemp = DS18X20(onewire_bus)
        return self._etemp
