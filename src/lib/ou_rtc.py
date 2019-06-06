from machine import RTC

from ds3231 import DS3231
import logging

_logger = logging.getLogger("rtc")

def time_reasonable(time_tuple):
    return time_tuple[0] >= 2019

class OuRtc(object):

    def __init__(self):
        _logger.debug("Initializing RTC")
        self.irtc = RTC()
        self.ertc = DS3231(0, pins=('P22','P21'))

        itime = self.irtc.now()
        etime = self.ertc.get_time()

        if not time_reasonable(itime):
            _logger.warning("Internal RTC not set: %s", itime)
        else:
            _logger.info("Internal RTC time: %s", itime)

        if not time_reasonable(etime):
            _logger.warning("External RTC not set: %s", etime)
        else:
            _logger.info("External RTC time: %s", etime)

    def get_time(self, set_internal_rtc=False):
        return self.ertc.get_time(set_rtc=set_internal_rtc)
