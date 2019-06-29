import time

from machine import RTC

import ntptime

SECONDS_1970_TO_2000 = time.mktime((2000,1,1,0,0,0,0,0))

def fetch_ntp_time():
    # NTP returns seconds since 1900
    # The ntptime lib adjusts that to seconds since 2000
    seconds_2000_to_now = ntptime.time()
    # The Pycom time lib uses seconds since 1970
    seconds_1970_to_now = SECONDS_1970_TO_2000 + seconds_2000_to_now
    return seconds_1970_to_now

def next_even_minutes(minutes_divisor, plus=0):
    tt = time.gmtime()
    minutes = tt[4]
    next_minutes = (minutes // minutes_divisor) * minutes_divisor + plus
    if next_minutes <= minutes:
        next_minutes += minutes_divisor
    # time.mktime() will handle minutes overflow as you would expect:
    # 14:70 -> 15:10
    next_tt = tt[0:4] + (next_minutes, 0, 0, 0)
    return next_tt

def next_time_of_day(hour, minute):
    tt = time.gmtime()
    hh = tt[3]
    mm = tt[4]
    if mm < minute:
        next_tt = tt[0:2] + (hh, minute, 0, 0, 0)
    else:
        next_tt = tt[0:3] + (hh+1, minute, 0, 0, 0)

    return next_tt

def seconds_until_time(next_tt):
    now = time.time()
    secs = time.mktime(next_tt) - now
    return secs
