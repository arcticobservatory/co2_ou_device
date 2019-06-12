import logging
import os
import time

from machine import Pin
from machine import RTC
from network import LTE
import explorir
import pycom

import time_util

_logger = logging.getLogger("co2unit_self_test")

FLAG_MOSFET_PIN = const(1<<0)
FLAG_SD_CARD    = const(1<<1)
FLAG_ERTC       = const(1<<2)
FLAG_FLASH_PIN  = const(1<<3)
FLAG_CO2        = const(1<<4)
FLAG_ETEMP      = const(1<<5)

FLAG_TIME_SOURCE    = const(1<<6)

FLAG_LTE_INIT           = const(1<<7)
FLAG_LTE_ATTACH         = const(1<<8)
FLAG_LTE_CONNECT        = const(1<<9)
FLAG_LTE_OPEN_SOCKET    = const(1<<10)
FLAG_LTE_SHUTDOWN       = const(1<<11)

FLAG_NTP_FETCH  = const(1<<12)

def quick_check(hw):
    _logger.info("Starting hardware quick check")

    failures = 0x0
    def log_error(flag, desc, e):
        failures |= flag
        _logger.warning("%s. %s: %s", desc, type(e).__name__, e)

    try:
        mosfet_pin = hw.mosfet_pin()
        mosfet_pin.mode(Pin.OUT)
        _logger.info("Mosfet pin state: %s", mosfet_pin())
    except Exception as e:
        log_error(FLAG_MOSFET_PIN, "Mosfet pin", e)

    try:
        sdcard = hw.sdcard()
        mountpoint = "/co2_sd_card_test"
        os.mount(sdcard, mountpoint)
        contents = os.listdir(mountpoint)
        os.unmount(mountpoint)
        _logger.info("SD card OK. Contents: %s", contents)
    except Exception as e:
        log_error(FLAG_SD_CARD, "SD card", e)

    try:
        ertc = hw.ertc()
        time_tuple = ertc.get_time()
        _logger.info("External RTC ok. Current time: %s", time_tuple)
    except Exception as e:
        log_error(FLAG_ERTC, "External RTC", e)

    try:
        flash_pin = hw.flash_pin()
        flash_state = flash_pin()
        _logger.info("Flash pin state: %s", flash_state)
    except Exception as e:
        log_error(FLAG_FLASH_PIN, "Flash pin", e)

    try:
        co2 = hw.co2()
        co2.set_mode(explorir.EXPLORIR_MODE_POLLING)
        reading = co2.read_co2()
        _logger.info("CO2 sensor ok. Current level: %d ppm", reading)
    except Exception as e:
        log_error(FLAG_CO2, "CO2 sensor", e)

    try:
        etemp = hw.etemp()
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
        log_error(FLAG_ETEMP, "External temp sensor", e)

    return failures

MAX_DRIFT = 4

def rtc_sanity_check(ertc):
    irtc = RTC()

    itime = irtc.now()
    etime = ertc.get_time()

    iok = itime[0] > 2010
    eok = etime[0] > 2010

    idrift = time.mktime(itime) - time.mktime(etime)

    _logger.debug("External RTC time: %s", etime)
    _logger.debug("Internal RTC time: %s (%d s)", itime, idrift)

    if eok and iok and abs(idrift) < MAX_DRIFT:
        _logger.info("Both RTCs ok. Internal drift acceptable (%d s, max %d s)", idrift, MAX_DRIFT)

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
        _logger.warning("Both RTCs reset; no reliable time source; %s", itime)
        return FLAG_TIME_SOURCE

    return 0

def show_boot_flags():
    _logger.info("pycom.lte_modem_en_on_boot(): %s", pycom.lte_modem_en_on_boot())
    _logger.info("pycom.wifi_on_boot():         %s", pycom.wifi_on_boot())
    _logger.info("pycom.wdt_on_boot():          %s", pycom.wdt_on_boot())
    _logger.info("pycom.heartbeat_on_boot():    %s", pycom.heartbeat_on_boot())

def test_lte_ntp(ertc):
    _logger.info("Testing LTE connectivity...")

    def log_error(desc, e):
        _logger.warning("%s. %s: %s", desc, type(e).__name__, e)

    start_ticks = time.ticks_ms()
    try:
        lte = LTE()
    except Exception as e:
        log_error("LTE constructor failed", e)
        return FLAG_LTE_INIT
    elapsed = time.ticks_diff(start_ticks, time.ticks_ms())

    _logger.info("LTE init ok (%d ms). Attaching... (up to 2 minutes)", elapsed)

    start_ticks = time.ticks_ms()
    try:
        lte.attach()
        while True:
            elapsed = time.ticks_diff(start_ticks, time.ticks_ms())
            if lte.isattached(): break
            if elapsed > 120 * 1000: raise TimeoutError()
    except Exception as e:
        log_error("LTE attach failed", e)
        return FLAG_LTE_ATTACH

    _logger.info("LTE attach ok (%d ms). Connecting...", elapsed)

    start_ticks = time.ticks_ms()
    try:
        lte.connect()
        while True:
            elapsed = time.ticks_diff(start_ticks, time.ticks_ms())
            if lte.isconnected():
                break
            elif elapsed > 120 * 1000:
                raise TimeoutError("LTE did not attach after %d ms" % elapsed)
    except Exception as e:
        log_error("LTE connect failed", e)
        return FLAG_LTE_CONNECT

    _logger.info("LTE connect ok (%d ms). Getting time with NTP...", elapsed)

    start_ticks = time.ticks_ms()
    try:
        irtc = RTC()
        ts = time_util.fetch_ntp_time()
        idrift = ts - time.mktime(irtc.now())
        if abs(idrift) < MAX_DRIFT:
            _logger.info("Drift from NTP: %s s; within threshold (%d s)", idrift, MAX_DRIFT)
        else:
            ntp_tuple = time.gmtime(ts)
            irtc = RTC()
            irtc.init(ntp_tuple)
            ertc.save_time()
            _logger.info("RTC set from NTP %s; drift was %d s", ntp_tuple, idrift)
    except Exception as e:
        log_error("NTP fetch failed", e)
        return FLAG_NTP_FETCH
    elapsed = time.ticks_diff(start_ticks, time.ticks_ms())

    _logger.info("Got time with NTP (%d ms). Shutting down...", elapsed)

    start_ticks = time.ticks_ms()
    try:
        lte.disconnect()
        lte.dettach()
        lte.deinit()
    except Exception as e:
        log_error("NTP disconnect/detach/deinit failed", e)
        return FLAG_LTE_SHUTDOWN
    elapsed = time.ticks_diff(start_ticks, time.ticks_ms())

    _logger.info("LTE deactivated (%d ms)", elapsed)
    return 0
