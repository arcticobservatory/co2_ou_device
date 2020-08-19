import logging
import os
import time

from machine import Pin
from machine import SPI
from machine import UART
from machine import RTC
import machine
import pycom

_logger = logging.getLogger("co2unit_hw")
#_logger.setLevel(logging.DEBUG)

class NoSdCardError(Exception): pass

PINSET_PRODUCTION = const(0)
PINSET_BREADBOARD = const(1)

def pinset_on_boot(pinset):
    return pycom.nvs_set("co2unit_pinset", pinset)

class Co2UnitHw(object):
    SDCARD_MOUNT_POINT = "/sd"

    def __init__(self):
        self._power_peripherals = None
        self._mosfet_pin = None
        self._sdcard = None
        self._ertc = None
        self._flash_pin = None
        self._co2 = None
        self._etemp = None
        self.sd_mounted = False

        try:
            pinset = pycom.nvs_get("co2unit_pinset")
        except ValueError:
            # Some firmwares raise a ValueError if not set
            pinset = PINSET_PRODUCTION
        if not pinset:
            # Some firmwares return None if not set
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

        else:
            raise ValueError("Unknown pinset value %s" % (pinset))

    @property
    def mosfet_pin(self):
        if not self._mosfet_pin and self._mosfet_pin_name:
            self._mosfet_pin = Pin(self._mosfet_pin_name, mode=Pin.OUT)
        return self._mosfet_pin

    @property
    def sdcard(self):
        if not self._sdcard:
            _logger.debug("Initializing SD card")
            import pycom_util
            import sdcard
            self._spi = pycom_util.SpiWrapper()
            self._spi.init(SPI.MASTER)
            try:
                self._sdcard = sdcard.SDCard(self._spi, machine.Pin(self._sd_cs_pin_name))
            except OSError as e:
                if "no sd card" in str(e).lower():
                    raise NoSdCardError(e)
                else:
                    raise
        return self._sdcard

    @property
    def ertc(self):
        if not self._ertc:
            _logger.debug("Initializing external RTC")
            from ds3231 import DS3231
            self._ertc = DS3231(0, pins=self._i2c_pins_names)
        return self._ertc

    @property
    def flash_pin(self):
        if not self._flash_pin:
            self._flash_pin = Pin(self._flash_pin_name)
        return self._flash_pin

    def set_wake_on_flash_pin(self):
        # Flash pin goes low on light detection
        if self.flash_pin() == 1:
            _logger.warning("Light sensor is still triggered. Skipping wakeup to avoid an infinite wake loop.")
        else:
            pins = [self._flash_pin_name]
            _logger.info("Setting wakeup on %s", pins)
            machine.pin_sleep_wakeup(pins=pins, mode=machine.WAKEUP_ANY_HIGH)

    @property
    def co2(self):
        if not self._co2:
            _logger.debug("Initializing co2 sensor")
            import explorir
            uart = UART(*self._co2_uart_params)
            self._co2 = explorir.ExplorIr(uart)
        return self._co2

    @property
    def etemp(self):
        if not self._etemp:
            _logger.debug("Initializing external temp sensor")
            import onewire
            onewire_bus = onewire.OneWire(Pin(self._onewire_pin_name))
            self._etemp = onewire.DS18X20(onewire_bus)
        return self._etemp

    def power_peripherals(self, value=None):
        if value != None:
            if self.mosfet_pin == None:
                _logger.info("No mosfet pin on this build")
            else:
                _logger.info("Setting power pin %s", value)
                self.mosfet_pin(value)
            self._power_peripherals = value

        return self._power_peripherals

    def sync_to_most_reliable_rtc(self, max_drift_secs=4, reset_ok=False):
        irtc = machine.RTC()
        ertc = self.ertc

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
            msg = "Both RTCs reset; no reliable time source; %s" % (itime,)
            if reset_ok:
                _logger.warning(msg)
            else:
                raise Exception(msg)

    def set_both_rtcs(self, ts, max_drift_secs=4):
        irtc = machine.RTC()
        ertc = self.ertc

        idrift = ts - time.mktime(irtc.now())

        if abs(idrift) < max_drift_secs:
            _logger.info("Drift: %s s; within threshold (%d s)", idrift, max_drift_secs)
        else:
            tt = time.gmtime(ts)
            irtc.init(tt)
            ertc.save_time()
            _logger.info("RTCs set %s; drift was %d s", tt, idrift)

    def mount_sd_card(self):
        if not self.sd_mounted:
            _logger.info("Mounting SD card")
            os.mount(self.sdcard, self.SDCARD_MOUNT_POINT)
        else:
            _logger.debug("SD card already mounted")
        self.sd_mounted = True

    def prepare_for_shutdown(self):
        if self.sd_mounted:
            _logger.info("Unmounting SD card")
            try:
                os.umount(self.SDCARD_MOUNT_POINT)
            except:
                _logger.exception("Could not unmount SD card")

        try:
            self.power_peripherals(False)
        except:
            _logger.exception("Could not cut power to peripherals")

        try:
            self.set_wake_on_flash_pin()
        except:
            _logger.exception("Could not set wake on flash pin")
