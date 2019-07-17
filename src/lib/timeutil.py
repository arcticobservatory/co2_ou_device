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
    yy, mo, dd, hh, mm = tt[0:5]
    next_minutes = (mm // minutes_divisor) * minutes_divisor + plus
    if next_minutes <= mm:
        next_minutes += minutes_divisor
    # time.mktime() will handle minutes overflow as you would expect:
    # e.g. 14:70 -> 15:10
    next_tt = (yy, mo, dd, hh, next_minutes, 0, 0, 0)
    return next_tt

def next_time_of_day(hour, minute):
    tt = time.gmtime()
    yy, mo, dd, hh, mm = tt[0:5]
    if hh <= hour and mm < minute:
        next_tt = (yy, mo, dd, hour, minute, 0, 0, 0)
    else:
        next_tt = (yy, mo, dd+1, hour, minute, 0, 0, 0)

    return next_tt

def seconds_until_time(next_tt):
    now = time.time()
    secs = time.mktime(next_tt) - now
    return secs
