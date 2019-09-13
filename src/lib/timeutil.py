import time
import machine

class DummyWdt(object):
    def init(self, timeout): pass
    def feed(self): pass

def format_time(tt):
    yy, mo, dd, hh, mm, ss, _, _ = tt
    return "{:04}-{:02}-{:02} {:02}:{:02}:{:02}".format(yy,mo,dd,hh,mm,ss)

def fetch_ntp_time():
    import ntptime
    SECONDS_1970_TO_2000 = time.mktime((2000,1,1,0,0,0,0,0))
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

def add_random_minutes(tt, upperbound):
    yy, mo, dd, hh, mm, ss, wd, yd = tt
    rand_ss = machine.rng() % (upperbound*60)
    return (yy, mo, dd, hh, mm, ss+rand_ss, wd, yd)

def next_minutes_random(minutes_divisor, offset1, offset2):
    # We must be careful to only schedule once in the given window.
    # So first, schedule by the start of the window first, so it will wrap to
    # the next window if we are inside the window already. And only then, add
    # the randomness
    tt = next_even_minutes(minutes_divisor, offset1)
    return add_random_minutes(tt, offset2-offset1)

def next_time_of_day(hour, minute):
    tt = time.gmtime()
    yy, mo, dd, hh, mm = tt[0:5]
    if hh <= hour and mm < minute:
        next_tt = (yy, mo, dd, hour, minute, 0, 0, 0)
    else:
        next_tt = (yy, mo, dd+1, hour, minute, 0, 0, 0)

    return next_tt

def next_time_of_day_random(hour, m1, m2):
    tt = next_time_of_day(hour, m1)
    return add_random_minutes(tt, m2-m1)

def seconds_until_time(next_tt):
    now = time.time()
    secs = time.mktime(next_tt) - now
    return secs
