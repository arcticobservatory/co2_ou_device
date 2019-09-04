import logging
import sys
import time

import fileutil

_logger = logging.getLogger("errors")
#_logger.setLevel(logging.DEBUG)

def _record(hw, level, msg, exc=None):
    _logger.debug("Attempting to write error in log on SD card...")

    if not hw.power_peripherals():
        hw.power_peripherals(True)
        _logger.info("Giving hardware a moment after power on")
        time.sleep_ms(100)

    hw.sync_to_most_reliable_rtc(reset_ok=True)
    hw.mount_sd_card()

    errors_dir = hw.SDCARD_MOUNT_POINT + "/errors"
    errors_match = ("errors-", ".txt")

    target = fileutil.prep_append_file(dir=errors_dir, match=errors_match)

    tt = time.gmtime()
    try:
        import timeutil
        tt = timeutil.format_time(tt)
    except:
        pass

    with open(target, "at") as f:
        f.write("----- {} {:5} {}\n".format(tt, level, msg))
        if exc:
            sys.print_exception(exc, f)
    _logger.info("Recorded error successfully to %s", target)

def record_error(hw, exc, msg):
    _record(hw, "EXC", msg, exc)

def warning(hw, msg):
    _record(hw, "WARN", msg)

def info(hw, msg):
    _record(hw, "INFO", msg)
