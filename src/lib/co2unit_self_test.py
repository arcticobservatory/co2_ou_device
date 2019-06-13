import logging
import time

import pycom


_logger = logging.getLogger("co2unit_self_test")

FLAG_MOSFET_PIN     = const(1<<0)
FLAG_SD_CARD        = const(1<<1)
FLAG_ERTC           = const(1<<2)
FLAG_CO2            = const(1<<3)
FLAG_ETEMP          = const(1<<4)

FLAG_TIME_SOURCE    = const(1<<5)

FLAG_LTE_FW_API     = const(1<<6)   # If run on factory FW, the LTE API will be missing
FLAG_LTE_INIT       = const(1<<7)
FLAG_LTE_ATTACH     = const(1<<8)
FLAG_LTE_CONNECT    = const(1<<9)
FLAG_NTP_FETCH      = const(1<<10)
FLAG_LTE_SHUTDOWN   = const(1<<11)

failures = 0x0

def color_for_flag(flag):
    if flag==0: return 0x0
    elif flag==FLAG_MOSFET_PIN     : return 0x0
    elif flag==FLAG_SD_CARD        : return 0x440000
    elif flag==FLAG_ERTC           : return 0x004400
    elif flag==FLAG_CO2            : return 0x004400
    elif flag==FLAG_ETEMP          : return 0x004400

    elif flag==FLAG_TIME_SOURCE    : return 0x442200

    elif flag==FLAG_LTE_FW_API     : return 0x000011
    elif flag==FLAG_LTE_INIT       : return 0x000022
    elif flag==FLAG_LTE_ATTACH     : return 0x002222
    elif flag==FLAG_LTE_CONNECT    : return 0x004422
    elif flag==FLAG_NTP_FETCH      : return 0x006622
    elif flag==FLAG_LTE_SHUTDOWN   : return 0x000022

    else: return 0x0

class CheckStep(object):
    def __init__(self, flag, suppress_exception=False):
        self.flag = flag
        self.suppress_exception = suppress_exception
        self.start_ticks = None
        self.extra_fmt_str = None
        self.extra_args = None

    def __enter__(self):
        pycom.rgbled(color_for_flag(self.flag))
        _logger.debug("%08x...", self.flag)
        self.start_ticks = time.ticks_ms()

    def __exit__(self, exc_type, exc_value, traceback):
        global failures
        elapsed = time.ticks_diff(self.start_ticks, time.ticks_ms())
        pycom.rgbled(0x0)
        if exc_type:
            failures |= self.flag
            _logger.warning("%08x failed (%d ms). %s: %s", self.flag, elapsed, exc_type, exc_value)
            if self.suppress_exception:
                return True
        else:
            failures &= ~self.flag
            _logger.debug("%08x OK (%d ms)", self.flag, elapsed)

def quick_check(hw):

    _logger.info("Starting hardware quick check")

    with CheckStep(FLAG_MOSFET_PIN, suppress_exception=True):
        mosfet_pin = hw.mosfet_pin()
        _logger.info("Mosfet pin state: %s", mosfet_pin())

    with CheckStep(FLAG_SD_CARD, suppress_exception=True):
        import os
        sdcard = hw.sdcard()
        mountpoint = "/co2_sd_card_test"
        os.mount(sdcard, mountpoint)
        contents = os.listdir(mountpoint)
        os.unmount(mountpoint)
        _logger.info("SD card OK. Contents: %s", contents)

    with CheckStep(FLAG_ERTC, suppress_exception=True):
        ertc = hw.ertc()
        time_tuple = ertc.get_time()
        _logger.info("External RTC ok. Current time: %s", time_tuple)

    with CheckStep(FLAG_CO2, suppress_exception=True):
        import explorir
        co2 = hw.co2()
        co2.set_mode(explorir.EXPLORIR_MODE_POLLING)
        reading = co2.read_co2()
        _logger.info("CO2 sensor ok. Current level: %d ppm", reading)

    with CheckStep(FLAG_ETEMP, suppress_exception=True):
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

    with CheckStep(FLAG_TIME_SOURCE, suppress_exception=True):
        hw.sync_to_most_reliable_rtc()

    global failures
    return failures

def show_boot_flags():
    _logger.info("pycom.wifi_on_boot():         %s", pycom.wifi_on_boot())
    with CheckStep(FLAG_LTE_FW_API, suppress_exception=True):
        _logger.info("pycom.lte_modem_en_on_boot(): %s", pycom.lte_modem_en_on_boot())
        _logger.info("pycom.wdt_on_boot():          %s", pycom.wdt_on_boot())
        _logger.info("pycom.heartbeat_on_boot():    %s", pycom.heartbeat_on_boot())

def test_lte_ntp(hw, max_drift_secs=4):

    global failures
    _logger.info("Testing LTE connectivity...")

    def log_error(desc, e):
        _logger.warning("%s. %s: %s", desc, type(e).__name__, e)

    try:
        with CheckStep(FLAG_LTE_FW_API):
            from network import LTE

        start_ticks = time.ticks_ms()
        with CheckStep(FLAG_LTE_INIT):
            lte = LTE()
        elapsed = time.ticks_diff(start_ticks, time.ticks_ms())
        _logger.info("LTE init ok (%d ms). Attaching... (up to 2 minutes)", elapsed)
    except:
        return failures

    try:
        with CheckStep(FLAG_LTE_ATTACH):
            start_ticks = time.ticks_ms()
            lte.attach()
            while True:
                elapsed = time.ticks_diff(start_ticks, time.ticks_ms())
                if lte.isattached(): break
                if elapsed > 150 * 1000: raise TimeoutError()
            _logger.info("LTE attach ok (%d ms). Connecting...", elapsed)

        with CheckStep(FLAG_LTE_CONNECT):
            start_ticks = time.ticks_ms()
            lte.connect()
            while True:
                elapsed = time.ticks_diff(start_ticks, time.ticks_ms())
                if lte.isconnected():
                    break
                elif elapsed > 120 * 1000:
                    raise TimeoutError("LTE did not attach after %d ms" % elapsed)
            _logger.info("LTE connect ok (%d ms). Getting time with NTP...", elapsed)

        with CheckStep(FLAG_NTP_FETCH, suppress_exception=True):
            from machine import RTC
            import time_util

            start_ticks = time.ticks_ms()
            irtc = RTC()
            ts = time_util.fetch_ntp_time()
            idrift = ts - time.mktime(irtc.now())
            if abs(idrift) < max_drift_secs:
                _logger.info("Drift from NTP: %s s; within threshold (%d s)", idrift, max_drift_secs)
            else:
                ntp_tuple = time.gmtime(ts)
                irtc = RTC()
                irtc.init(ntp_tuple)
                hw.ertc().save_time()
                _logger.info("RTC set from NTP %s; drift was %d s", ntp_tuple, idrift)
            _logger.info("Got time with NTP (%d ms). Shutting down...", elapsed)

        with CheckStep(FLAG_LTE_SHUTDOWN):
            start_ticks = time.ticks_ms()
            lte.disconnect()
            lte.dettach()
            lte.deinit()
            elapsed = time.ticks_diff(start_ticks, time.ticks_ms())
            _logger.info("LTE deactivated (%d ms)", elapsed)
    except:
        pass

    return failures
