import logging
import sys
import time

import fileutil

_logger = logging.getLogger("errors")
#_logger.setLevel(logging.DEBUG)

def record_error(hw, exc, msg):
    _logger.debug("Attempting to write error in log on SD card...")
    if not hw.power_peripherals():
        hw.power_peripherals(True)
        _logger.info("Giving the SD card a moment to boot...")
        time.sleep_ms(100)
    hw.mount_sd_card()

    errors_dir = hw.SDCARD_MOUNT_POINT + "/errors"
    errors_match = ("errors-", ".txt")

    target = fileutil.prep_append_file(dir=errors_dir, match=errors_match)

    with open(target, "at") as f:
        f.write("----- {}\n".format(time.gmtime()))
        f.write("{}\n".format(msg))
        sys.print_exception(exc, f)
    _logger.info("Recorded error successfully to %s", target)
