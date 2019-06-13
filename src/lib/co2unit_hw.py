import logging
import time

from machine import Pin
from machine import SPI
from machine import UART
from machine import RTC
import pycom

from ds3231 import DS3231
from onewire import DS18X20
from onewire import OneWire
import explorir
import sdcard

_logger = logging.getLogger("co2unit_hw")

class NoSdCardError(Exception): pass

PINSET_PRODUCTION = const(0)
PINSET_BREADBOARD = const(1)

def pinset_on_boot(pinset):
    return pycom.nvs_set("co2unit_pinset", pinset)

class Co2UnitHw(object):
    def __init__(self):
        self._mosfet_pin = None
        self._sdcard = None
        self._ertc = None
        self._flash_pin = None
        self._co2 = None
        self._etemp = None

        try:
            pinset = pycom.nvs_get("co2unit_pinset")
        except ValueError:
            pinset = PINSET_PRODUCTION

        # Note: The P2 pin also controls the RGB LED on Pycom devices
        #
        # - Once initialized with Pin(), pycom.rgbled() will have no effect
        # - No exception, just silent failure
        # - I do not know of an offical way to re-initialize the LED
        # - Turning the heartbeat on and off again seems to work in the REPL
        # - I haven't had luck getting it to work in scripts

        if pinset == PINSET_PRODUCTION:
            _logger.debug("Selecting pins for production unit")
            self._co2_uart_params = (1, 9600)
            self._i2c_pins_names = ('P22', 'P21')

            self._onewire_pin_name = 'P23'
            self._sd_cs_pin_name = 'P9'
            self._flash_pin_name = 'P2'     # Also used for RGB LED
            self._mosfet_pin_name = 'P12'

        elif pinset == PINSET_BREADBOARD:
            _logger.debug("Selecting pins for breadboard unit")
            self._co2_uart_params = (1, 9600)
            self._i2c_pins_names = ('P22', 'P21')

            self._onewire_pin_name = 'G15'
            self._sd_cs_pin_name = 'P12'
            self._flash_pin_name = 'P4'
            self._mosfet_pin_name = None

    def mosfet_pin(self):
        if not self._mosfet_pin and self._mosfet_pin_name:
            self._mosfet_pin = Pin(self._mosfet_pin_name, mode=Pin.OUT)
        return self._mosfet_pin

    def sdcard(self):
        if not self._sdcard:
            _logger.debug("Initializing SD card")
            self._spi = SPI(0, mode=SPI.MASTER)
            try:
                self._sdcard = sdcard.SDCard(self._spi, Pin(self._sd_cs_pin_name))
            except OSError as e:
                if "no sd card" in str(e).lower():
                    raise NoSdCardError(e)
                else:
                    raise
        return self._sdcard

    def ertc(self):
        if not self._ertc:
            _logger.debug("Initializing external RTC")
            self._ertc = DS3231(0, pins=self._i2c_pins_names)
        return self._ertc

    def flash_pin(self):
        if not self._flash_pin:
            self._flash_pin = Pin(self._flash_pin_name)
        return self._flash_pin

    def co2(self):
        if not self._co2:
            _logger.debug("Initializing co2 sensor")
            uart = UART(*self._co2_uart_params)
            self._co2 = explorir.ExplorIr(uart, scale=10)
        return self._co2

    def etemp(self):
        if not self._etemp:
            _logger.debug("Initializing external temp sensor")
            onewire_bus = OneWire(Pin(self._onewire_pin_name))
            self._etemp = DS18X20(onewire_bus)
        return self._etemp

    def power_peripherals(self, value=None):
        mosfet_pin = self.mosfet_pin()
        if mosfet_pin == None:
            _logger.debug("No mosfet pin on this build")
            return value
        else:
            return mosfet_pin(value)

    def sync_to_most_reliable_rtc(self, max_drift_secs=4):
        irtc = RTC()
        ertc = self.ertc()

        itime = irtc.now()
        etime = ertc.get_time()

        iok = itime[0] > 2010
        eok = etime[0] > 2010

        idrift = time.mktime(itime) - time.mktime(etime)

        _logger.debug("External RTC time: %s", etime)
        _logger.debug("Internal RTC time: %s (%d s)", itime, idrift)

        if eok and iok and abs(idrift) < max_drift_secs:
            _logger.info("Both RTCs ok. Internal drift acceptable (%d s, max %d s)", idrift, max_drift_secs)
        elif eok and iok:
            _logger.info("Internal RTC has drifted %d s; setting from external %s", idrift, etime)
            etime = ertc.get_time(set_rtc=True)
        elif eok:
            _logger.info("Internal RTC reset; setting from external %s", etime)
            etime = ertc.get_time(set_rtc=True)
        elif iok:
            _logger.info("External RTC reset; setting from internal %s", itime)
            ertc.save_time()
        else:
            raise Exception("Both RTCs reset; no reliable time source; %s" % itime)
