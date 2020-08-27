import utime as time
try:
    import machine
except:
    import mock_apis
    machine = mock_apis.MockMachine()

class DummyWdt(object):
    def init(self, timeout): pass
    def feed(self): pass

def format_time(tt):
    yy, mo, dd, hh, mm, ss, *_ = tt
    return "{:04}-{:02}-{:02} {:02}:{:02}:{:02}".format(yy,mo,dd,hh,mm,ss)

def parse_time(iso):
    try:
        dt = iso.split(" ")
        yy, mo, dd = dt[0].split("-")

        if len(dt) == 2:
            hh, mm, ss = dt[1].split(":")
        else:
            hh, mm, ss = (0, 0, 0)

        tt = tuple([int(part) for part in [yy,mo,dd,hh,mm,ss,0,0]])
        return tt
    except Exception as e:
        raise ValueError("Could not parse time %r: %s" % (iso, e))

def isleapyear(yy):
    return yy % 4 == 0 and (yy % 100 != 0 or yy % 400 == 0)

def days_in_month(yy, mo):
    mon_days = [None,
                31, 29 if isleapyear(yy) else 28, 31, 30, 31, 30, 31,
                31, 30, 31, 30, 31]
    while mo > 12:
        mo -= 12
        yy += 1
    return mon_days[mo]

def mktime(tt):
    "Convert time tuple to seconds offset"
    if hasattr(time, "mktime"):
        # Use system's mktime if available
        return time.mktime(tt)
    else:
        # Implement if not available (e.g. vanilla MicroPython's Unix port)
        yy, mo, dd, hh, mm, ss, *_ = tt

        epoch = 1970
        ts = (yy-epoch) * 365 * 24 * 60 * 60
        for year in range(epoch,yy):
            if isleapyear(year):
                ts += 24*60*60

        for month in range(1,mo):
            ts += days_in_month(yy,month) * 24 * 60 * 60

        ts += (dd-1) * 24 * 60 * 60
        ts += hh * 60 * 60
        ts += mm * 60
        ts += ss
        return ts

def localtime(ts):
    if hasattr(time, "mktime"):
        # Use system's localtime if mktime is available
        return time.localtime(ts)
    else:
        # The trouble is that the Unix port's localtime quietly takes
        # into account the system's time zone including DST.
        # If we want it to mirror the primitive implementation of mktime,
        # we have to write a matching primitive version of localtime
        yy = 1970
        while True:
            yeardays = 366 if isleapyear(yy) else 365
            yearsecs = yeardays * 24 * 60 * 60
            if ts < yearsecs:
                break
            ts -= yearsecs
            yy += 1

        mo = 1
        while True:
            monsecs = days_in_month(yy, mo) * 24 * 60 * 60
            if ts < monsecs:
                break
            ts -= monsecs
            mo += 1

        daysecs = 24 * 60 * 60
        dd = 1 + ts // daysecs
        ts = ts % daysecs

        hoursecs = 60 * 60
        hh = ts // hoursecs
        ts = ts % hoursecs

        mm = ts // 60
        ss = ts % 60

        return (yy, mo, dd, hh, mm, ss, 0, 0)

def normalize(tt):
    return localtime(mktime(tt))

def fetch_ntp_time(ntp_host=None):
    import ntptime
    if ntp_host:
        ntptime.host = ntp_host
    SECONDS_1970_TO_2000 = time.mktime((2000,1,1,0,0,0,0,0))
    # NTP returns seconds since 1900
    # The ntptime lib adjusts that to seconds since 2000
    seconds_2000_to_now = ntptime.time()
    # The Pycom time lib uses seconds since 1970
    seconds_1970_to_now = SECONDS_1970_TO_2000 + seconds_2000_to_now
    return seconds_1970_to_now

# TODO: Remove these schedule functions in favor of schedule.py

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
