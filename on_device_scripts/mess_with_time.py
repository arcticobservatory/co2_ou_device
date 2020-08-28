import co2unit_hw
import utime as time
import machine
import timeutil

hw = co2unit_hw.Co2UnitHw()
hw.power_peripherals(True)
time.sleep_ms(100)

irtc = machine.RTC()
ertc = hw.ertc

itime = irtc.now()
etime = ertc.get_time()

idrift = time.mktime(itime) - time.mktime(etime)

print("External RTC time:", etime)
print("Internal RTC time:", itime, idrift)

# Set internal from external
etime = ertc.get_time(set_rtc=True)

# Round off minutes to a measurement time
yy, mo, dd, hh, mm, ss, *_ = etime
even_mm = mm // 30 * 30
even_tt = timeutil.normalize((yy, mo, dd, hh, even_mm, 0, 0,0))
before_tt = timeutil.normalize((yy, mo, dd, hh, even_mm-2, 0, 0,0))
after_tt = timeutil.normalize((yy, mo, dd, hh, even_mm+2, 0, 0,0))

def set_both(itt, ett):
    print("=== Setting new times ... ===")
    # First set internal, so we can set external from it
    irtc.init(ett)
    # Set external from internal
    ertc.save_time()
    # Set interal again
    irtc.init(itt)
    print("External RTC time:", ett)
    print("Internal RTC time:", itt)

# Ready to go
#set_both(itt=even_tt, ett=even_tt)

# Woke up early
set_both(itt=even_tt, ett=before_tt)

# Woke up late
#set_both(itt=even_tt, ett=after_tt)
