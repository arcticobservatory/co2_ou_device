import time

from machine import RTC

import ntptime

from ds3231 import DS3231
import logging

_logger = logging.getLogger("rtc")

MAX_DRIFT = 4
SECONDS_1970_TO_2000 = time.mktime((2000,1,1,0,0,0,0,0))

def time_reasonable(time_tuple=None):
    time_tuple = time_tuple or time.gmtime()
    return time_tuple[0] >= 2019

def fetch_ntp_time():
    # NTP returns seconds since 1900
    # The ntptime lib adjusts that to seconds since 2000
    seconds_2000_to_now = ntptime.time()
    # The Pycom time lib uses seconds since 1970
    seconds_1970_to_now = SECONDS_1970_TO_2000 + seconds_2000_to_now
    return seconds_1970_to_now

class OuRtc(object):

    def __init__(self):
        _logger.debug("Initializing RTCs")
        self.irtc = RTC()
        self.ertc = DS3231(0, pins=('P22','P21'))

    def compare_and_adjust(self, itime=None, etime=None):
        itime = itime or self.irtc.now()
        etime = etime or self.ertc.get_time()

        _logger.debug("Initial internal RTC time: %s", itime)
        _logger.debug("Initial external RTC time: %s", etime)

        iok = time_reasonable(itime)
        eok = time_reasonable(etime)

        idrift = time.mktime(itime) - time.mktime(etime)

        if eok and iok:
            _logger.debug("Both RTCs ok")
            if abs(idrift) < MAX_DRIFT:
                _logger.debug("Internal RTC drift: %s s; within threshold (±%s d)", idrift, MAX_DRIFT)
            else:
                _logger.info("Internal RTC drift: %d s; setting from external", idrift)
                self.set_internal_from_external()

        elif eok:
            _logger.info("Internal RTC reset; setting from external %s", etime)
            self.set_internal_from_external()
        elif iok:
            _logger.info("External RTC reset; setting from internal %s", itime)
            self.set_external_from_internal()
        else:
            _logger.warning("Both RTCs reset; no reliable time source")

    def set_internal(self, time_tuple):
        self.irtc.init(time_tuple)
        _logger.debug("New internal RTC time: %s", self.irtc.now())

    def set_internal_from_external(self):
        etime = self.ertc.get_time(set_rtc=True)
        _logger.debug("New internal RTC time: %s", self.irtc.now())

    def set_external_from_internal(self):
        self.ertc.save_time()
        _logger.debug("New external RTC time: %s", self.ertc.get_time())

    def set_from_ntp(self):
        _logger.debug("Fetching NTP time")
        ts = fetch_ntp_time()
        idrift = ts - time.mktime(self.irtc.now())
        if abs(idrift) < MAX_DRIFT:
            _logger.info("Drift from NTP: %s s; within threshold (±%s d)", idrift, MAX_DRIFT)
        else:
            # Set internal RTC from NTP
            ntp_tuple = time.gmtime(ts)
            self.irtc.init(ntp_tuple)
            # Set external RTC from internal
            self.ertc.save_time()
            _logger.info("RTC set from NTP %s; drift was %d s", ntp_tuple, idrift)
            _logger.debug("New internal RTC time: %s", self.irtc.now())
            _logger.debug("New external RTC time: %s", self.ertc.get_time())
