import logging
import os
import time

from machine import Pin

import explorir

_logger = logging.getLogger("co2unit_self_test")

FLAG_MOSFET_PIN = const(1<<0)
FLAG_SD_CARD    = const(1<<1)
FLAG_ERTC       = const(1<<2)
FLAG_FLASH_PIN  = const(1<<3)
FLAG_CO2        = const(1<<4)
FLAG_ETEMP      = const(1<<5)

def quick_check(hw):
    _logger.info("Starting hardware quick check")

    failures = 0x0
    def log_error(flag, desc, e):
        failures = failures | flag
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
