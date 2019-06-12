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

    def flash_pin(self):
        return self._flash_pin

    def ertc(self):
        if not self._ertc:
            _logger.debug("Initializing external RTC")
            self._ertc = DS3231(0, pins=self._i2c_pins)
        return self._ertc

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

    def quick_check(self):
        def log_error(msg, e):
            _logger.warning("%s. %s: %s", msg, type(e).__name__, e)

        try:
            mosfet_pin = self.mosfet_pin()
            mosfet_pin.mode(Pin.OUT)
            _logger.info("Mosfet pin initial state: %s", mosfet_pin())
            _logger.info("Mosfet pin: turning on")
            mosfet_pin(True)
            _logger.info("Mosfet pin new state: %s", mosfet_pin())
        except Exception as e:
            log_error("Mosfet pin failure", e)

        try:
            ertc = self.ertc()
            time_tuple = ertc.get_time()
            _logger.info("External RTC ok. Current time: %s", time_tuple)
        except Exception as e:
            log_error("External RTC failure", e)

        try:
            import os
            sdcard = self.sdcard()
            mountpoint = "/co2_sd_card_test"
            os.mount(sdcard, mountpoint)
            contents = os.listdir(mountpoint)
            os.unmount(mountpoint)
            _logger.info("SD card OK. Contents: %s", contents)
        except Exception as e:
            log_error("SD card failure", e)

        try:
            flash_pin = self.flash_pin()
            flash_state = flash_pin()
            _logger.info("Flash pin state: %s", flash_state)
        except Exception as e:
            log_error("Flash pin failure failure", e)

        try:
            co2 = self.co2()
            co2.set_mode(explorir.EXPLORIR_MODE_POLLING)
            reading = co2.read_co2()
            _logger.info("CO2 sensor ok. Current level: %d ppm", reading)
        except Exception as e:
            log_error("CO2 sensor failure", e)

        try:
            import time
            etemp = self.etemp()
            _logger.debug("Starting external temp read. Can take up to 750ms.")
            etemp.start_conversion()
            start_ticks = time.ticks_ms()
            while True:
                reading = etemp.read_temp_async()
                if reading: break
                elapsed = time.ticks_diff(start_ticks, time.ticks_ms())
                if elapsed > 1000:
                    raise TimeoutError("Timeout reading external temp sensor after %d ms", elapsed)
            _logger.info("External temp sensor ok. Current temp: %s C", reading)
        except Exception as e:
            log_error("External temp sensor failure", e)
