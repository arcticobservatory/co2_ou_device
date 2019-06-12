import time
import logging

import pycom

import ou_comm
import ou_rtc
import ou_sensors
import ou_storage

_logger = logging.getLogger("POST")

STATE_COLORS = {
        "POST_IN_PROGRESS": 0x442200,
        "TRYING_LTE": 0x000044,
        "LTE_CONNECTED": 0x002244,
        "OK": 0x008800,
        "ERRORS": 0x880000,
        "RESETTING": 0x442200,
        }

ERROR_COLORS = {
        "NO_SD_CARD": 0x440000,
        "OTHER_STORAGE_ERROR": 0x442200,
        "CANNOT_INIT_LTE": 0x000044,
        "OTHER_LTE_ERROR": 0x002244,
        "NO_TIME_SOURCE": 0x440044,
        "OTHER_RTC_ERROR": 0x442244,
        "OTHER_SENSOR_ERROR": 0x333333,
        }

def blink_rgbled(color, duration_ms=1000, speed_ms=100):
    loops = duration_ms // (2*speed_ms)
    for _ in range(0, loops):
        pycom.rgbled(color)
        time.sleep_ms(speed_ms)
        pycom.rgbled(0x000000)
        time.sleep_ms(speed_ms)

def show_errors(errors):
    if not errors:
        _logger.info("POST OK!")
        blink_rgbled(STATE_COLORS["OK"])

    else:
        _logger.info("POST errors: %s", errors)
        for _ in range(0,4):
            blink_rgbled(STATE_COLORS["ERRORS"])
            for error in errors:
                pycom.rgbled(ERROR_COLORS[error])
                time.sleep(1)
            pycom.rgbled(0x000000)
            time.sleep(1)

def errors_need_physical_fix(errors):
    return "NO_SD_CARD" in errors

def should_try_reset(errors):
    return "CANNOT_INIT_LTE" in errors

def post_on_boot(value=None):
    if value==None:
        try:
            return bool(pycom.nvs_get("ou_post_on_boot"))
        except ValueError:
            return False
    else:
        return pycom.nvs_set("ou_post_on_boot", int(value))

def do_post():
    pycom.heartbeat(False)
    pycom.rgbled(STATE_COLORS["POST_IN_PROGRESS"])
    _logger.info("Power-on Self Test")
    errors = []

    try:
        storage = ou_storage.OuStorage()
        storage.ensure_needed_dirs()
    except ou_storage.NoSdCardError as e:
        errors.append("NO_SD_CARD")
        _logger.error("No SD card present")
    except Exception as e:
        errors.append("OTHER_STORAGE_ERROR")
        _logger.error("Other storage error: %s: %s", type(e).__name__, e)

    try:
        rtc = ou_rtc.OuRtc()
        rtc.compare_and_adjust()
    except Exception as e:
        errors.append("OTHER_RTC_ERROR")
        _logger.error("Other RTC error: %s: %s", type(e).__name__, e)

    try:
        pycom.rgbled(STATE_COLORS["TRYING_LTE"])
        comm = ou_comm.OuComm()
        comm.set_persistent_settings()
        comm.lte_connect()
        pycom.rgbled(STATE_COLORS["LTE_CONNECTED"])
        rtc.set_from_ntp()
        comm.lte_disconnect()
        pycom.rgbled(STATE_COLORS["POST_IN_PROGRESS"])
    except ou_comm.InitModemError as e:
        errors.append("CANNOT_INIT_LTE")
        _logger.error("Cannot init LTE constructor: %s", e)
    except Exception as e:
        errors.append("OTHER_LTE_ERROR")
        _logger.error("Other LTE error: %s: %s", type(e).__name__, e)

    if not ou_rtc.time_reasonable():
        errors.append("NO_TIME_SOURCE")
        _logger.error("No time source")

    try:
        sensors = ou_sensors.OuSensors()
        reading = sensors.take_reading()
    except Exception as e:
        errors.append("OTHER_SENSOR_ERROR")
        _logger.error("Other sensor error: %s: %s", type(e).__name__, e)

    show_errors(errors)
    return errors
