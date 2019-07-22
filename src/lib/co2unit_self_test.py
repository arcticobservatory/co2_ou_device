import machine
import logging
import time

import pycom


_logger = logging.getLogger("co2unit_self_test")

FLAG_MOSFET_PIN     = const(1<<0)
FLAG_SD_CARD        = const(1<<1)

FLAG_ERTC           = const(1<<2)
FLAG_TIME_SOURCE    = const(1<<3)

FLAG_CO2            = const(1<<4)
FLAG_ETEMP          = const(1<<5)

FLAG_LTE_FW_API     = const(1<<6)   # If run on factory FW, the LTE API will be missing
FLAG_LTE_INIT       = const(1<<7)
FLAG_LTE_ATTACH     = const(1<<8)
FLAG_LTE_CONNECT    = const(1<<9)
FLAG_NTP_FETCH      = const(1<<10)
FLAG_LTE_SHUTDOWN   = const(1<<11)

FLAG_MAX_SHIFT      = const(16)

SETUP_INCOMPLETE_FLAGS = [FLAG_MOSFET_PIN, FLAG_SD_CARD, FLAG_ERTC, FLAG_CO2, FLAG_ETEMP, FLAG_LTE_FW_API]

failures = 0x0

def flag_color(flag):
    if flag==0: return 0x0
    elif flag==FLAG_MOSFET_PIN     : return 0x0
    elif flag==FLAG_SD_CARD        : return 0x440000

    elif flag==FLAG_ERTC           : return 0x441100
    elif flag==FLAG_TIME_SOURCE    : return 0x442200

    elif flag==FLAG_CO2            : return 0x004400
    elif flag==FLAG_ETEMP          : return 0x224400

    elif flag==FLAG_LTE_FW_API     : return 0x000011
    elif flag==FLAG_LTE_INIT       : return 0x000022
    elif flag==FLAG_LTE_ATTACH     : return 0x002222
    elif flag==FLAG_LTE_CONNECT    : return 0x004422
    elif flag==FLAG_NTP_FETCH      : return 0x006622
    elif flag==FLAG_LTE_SHUTDOWN   : return 0x000022

    else: return 0x0

def flag_name(flag):
    if flag==0                     : return "OK"
    elif flag==FLAG_MOSFET_PIN     : return "FLAG_MOSFET_PIN"
    elif flag==FLAG_SD_CARD        : return "FLAG_SD_CARD"

    elif flag==FLAG_ERTC           : return "FLAG_ERTC"
    elif flag==FLAG_TIME_SOURCE    : return "FLAG_TIME_SOURCE"

    elif flag==FLAG_CO2            : return "FLAG_CO2"
    elif flag==FLAG_ETEMP          : return "FLAG_ETEMP"

    elif flag==FLAG_LTE_FW_API     : return "FLAG_LTE_FW_API"
    elif flag==FLAG_LTE_INIT       : return "FLAG_LTE_INIT"
    elif flag==FLAG_LTE_ATTACH     : return "FLAG_LTE_ATTACH"
    elif flag==FLAG_LTE_CONNECT    : return "FLAG_LTE_CONNECT"
    elif flag==FLAG_NTP_FETCH      : return "FLAG_NTP_FETCH"
    elif flag==FLAG_LTE_SHUTDOWN   : return "FLAG_LTE_SHUTDOWN"

    else: raise Exception("Unknown flag {:#018b}".format(flag))

def blink_led(color, on_ms=100, off_ms=100, total_ms=1000):
    loops = total_ms // (on_ms+off_ms)
    for _ in range(0,loops):
        pycom.rgbled(color)
        time.sleep_ms(on_ms)
        pycom.rgbled(0x0)
        time.sleep_ms(off_ms)

def display_errors_led(flags = None):
    global failures
    flags = flags or failures

    wdt = machine.WDT(timeout=10*1000)

    if not flags:
        blink_led(0x004400)

    else:
        # Blink to show all errors
        for i in range(0,3):
            _logger.debug("failure loop %d", i)
            blink_led(0x440000)
            time.sleep_ms(200)
            for i in range(0,FLAG_MAX_SHIFT):
                flag = 1 << i
                color = flag_color(flag)
                if flags & flag and color:
                    pycom.rgbled(color)
                    _logger.debug("showing failure {:#018b}, color {:#08x}, {}".format(flag, color, flag_name(flag)))
                    time.sleep_ms(1000)
                    wdt.feed()
            pycom.rgbled(0x0)
            time.sleep_ms(200)

        # For fatal errors, freeze with light on for most prominent error
        for flag in SETUP_INCOMPLETE_FLAGS:
            if failures & flag:
                _logger.error("Hardware/firmware failure requires human intervention: %s", flag_name(flag))
                pycom.rgbled(flag_color(flag))
                for _ in range(0, 10):
                    time.sleep_ms(1000)
                    wdt.feed()
                break

    pycom.rgbled(0x0)

class CheckStep(object):
    def __init__(self, flag, suppress_exception=False):
        self.flag = flag
        self.flag_bin = "{flag:#0{width}b}".format(flag=flag, width=FLAG_MAX_SHIFT+2)
        self.flag_name = "{:20}".format(flag_name(flag))
        self.suppress_exception = suppress_exception
        self.chrono = machine.Timer.Chrono()
        self.extra_fmt_str = None
        self.extra_args = None

    def __enter__(self):
        pycom.rgbled(flag_color(self.flag))
        _logger.debug("%s %s ...", self.flag_bin, self.flag_name)
        self.chrono.start()

    def __exit__(self, exc_type, exc_value, traceback):
        global failures
        elapsed = self.chrono.read_ms()
        pycom.rgbled(0x0)
        if exc_type:
            failures |= self.flag
            _logger.warning(" %s %s failed (%d ms). %s: %s", self.flag_bin, self.flag_name, elapsed, exc_type, exc_value)
            if self.suppress_exception:
                return True
        else:
            failures &= ~self.flag
            _logger.debug("%s %s OK (%d ms)", self.flag_bin, self.flag_name, elapsed)

def show_boot_flags():
    _logger.info("pycom.wifi_on_boot():         %s", pycom.wifi_on_boot())
    with CheckStep(FLAG_LTE_FW_API, suppress_exception=True):
        # These methods are not available on old firmware versions
        # If they are missing, we need to upgrade the Pycom firmware
        _logger.info("pycom.lte_modem_en_on_boot(): %s", pycom.lte_modem_en_on_boot())
        _logger.info("pycom.wdt_on_boot():          %s", pycom.wdt_on_boot())
        _logger.info("pycom.heartbeat_on_boot():    %s", pycom.heartbeat_on_boot())

def quick_test_hw(hw):

    _logger.info("Starting hardware quick check")
    chrono = machine.Timer.Chrono()
    chrono.start()

    with CheckStep(FLAG_MOSFET_PIN, suppress_exception=True):
        mosfet_pin = hw.mosfet_pin()
        if mosfet_pin:
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
        chrono.reset()
        while True:
            reading = etemp.read_temp_async()
            if reading: break
            if chrono.read_ms() > 1000:
                raise TimeoutError("Timeout reading external temp sensor after %d ms" % chrono.read_ms())
        _logger.info("External temp sensor ok. Current temp: %s C", reading)

    show_boot_flags()
    _logger.info("Failures after quick hardware check: {:#018b}".format(failures))
    display_errors_led()

def test_lte_ntp(hw, max_drift_secs=4):

    wdt = machine.WDT(timeout=10*1000)

    global failures
    _logger.info("Testing LTE connectivity...")

    chrono = machine.Timer.Chrono()
    chrono.start()

    with CheckStep(FLAG_TIME_SOURCE, suppress_exception=True):
        hw.sync_to_most_reliable_rtc()

    lte = None

    try:
        with CheckStep(FLAG_LTE_FW_API):
            from network import LTE

        with CheckStep(FLAG_LTE_INIT):
            _logger.info("Init LTE...")
            chrono.reset()
            lte = LTE()
            _logger.info("LTE init ok (%d ms)", chrono.read_ms())
            wdt.feed()
    except:
        return failures

    try:
        with CheckStep(FLAG_LTE_ATTACH):
            _logger.info("LTE attaching... (up to 2 minutes)")
            chrono.reset()
            lte.attach()
            while True:
                wdt.feed()
                if lte.isattached(): break
                if chrono.read_ms() > 150 * 1000: raise TimeoutError("Timeout during LTE attach")
                time.sleep_ms(50)
            _logger.info("LTE attach ok (%d ms). Connecting...", chrono.read_ms())

        with CheckStep(FLAG_LTE_CONNECT):
            chrono.reset()
            lte.connect()
            while True:
                wdt.feed()
                if lte.isconnected(): break
                if chrono.read_ms() > 120 * 1000: raise TimeoutError("Timeout during LTE connect")
                time.sleep_ms(50)
            _logger.info("LTE connect ok (%d ms)", chrono.read_ms())

        with CheckStep(FLAG_NTP_FETCH, suppress_exception=True):
            from machine import RTC
            import timeutil

            chrono.reset()
            irtc = RTC()
            ts = timeutil.fetch_ntp_time()
            idrift = ts - time.mktime(irtc.now())
            if abs(idrift) < max_drift_secs:
                _logger.info("Drift from NTP: %s s; within threshold (%d s)", idrift, max_drift_secs)
            else:
                ntp_tuple = time.gmtime(ts)
                irtc = RTC()
                irtc.init(ntp_tuple)
                hw.ertc().save_time()
                _logger.info("RTC set from NTP %s; drift was %d s", ntp_tuple, idrift)
            failures &= ~FLAG_TIME_SOURCE   # Clear FLAG_TIME_SOURCE if previously set
            _logger.info("Got time with NTP (%d ms). Shutting down...", chrono.read_ms())
            wdt.feed()

        with CheckStep(FLAG_LTE_SHUTDOWN):
            if lte:
                try:
                    if lte.isconnected():
                        chrono.reset()
                        lte.disconnect()
                        _logger.info("LTE disconnected (%d ms)", chrono.read_ms())
                        wdt.feed()
                    if lte.isattached():
                        chrono.reset()
                        lte.dettach()
                        _logger.info("LTE detached (%d ms)", chrono.read_ms())
                        wdt.feed()
                finally:
                    chrono.reset()
                    lte.deinit()
                    _logger.info("LTE deinit-ed (%d ms)", chrono.read_ms())
                    wdt.feed()
    except:
        pass

    show_boot_flags()
    _logger.info("Failures after LTE test: {:#018b}".format(failures))
    display_errors_led()
