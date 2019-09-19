# Simple NTP client implementation
#
# Forked from the original MicroPython source
#   https://github.com/micropython/micropython/blob/master/ports/esp8266/modules/ntptime.py
#
# This fork adds a host parameter to time()
#   https://github.com/arcticobservatory/micropython/blob/ntp_host_param/ports/esp8266/modules/ntptime.py
#
# Submitted upstream as pull request #5122
#   https://github.com/micropython/micropython/pull/5122
#
# Original library is MIT licensed
# https://github.com/micropython/micropython/blob/master/LICENSE

try:
    import usocket as socket
except:
    import socket
try:
    import ustruct as struct
except:
    import struct

# (date(2000, 1, 1) - date(1900, 1, 1)).days * 24*60*60
NTP_DELTA = 3155673600

DEFAULT_HOST = "pool.ntp.org"

def time(host=None):
    if host==None:
        host = DEFAULT_HOST
    NTP_QUERY = bytearray(48)
    NTP_QUERY[0] = 0x1b
    addr = socket.getaddrinfo(host, 123)[0][-1]
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(1)
    res = s.sendto(NTP_QUERY, addr)
    msg = s.recv(48)
    s.close()
    val = struct.unpack("!I", msg[40:44])[0]
    return val - NTP_DELTA

# There's currently no timezone support in MicroPython, so
# utime.localtime() will return UTC time (as if it was .gmtime())
def settime():
    t = time()
    import machine
    import utime
    tm = utime.localtime(t)
    tm = tm[0:3] + (0,) + tm[3:6] + (0,)
    machine.RTC().datetime(tm)
