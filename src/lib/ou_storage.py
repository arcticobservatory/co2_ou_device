import os

from machine import Pin
from machine import SPI
from machine import SD

import logging
import sdcard

import fileutil
import flaky

_logger = logging.getLogger("ou_storage")

class OuStorageError(Exception): pass
class NoSdCardError(OuStorageError): pass
class SdMountError(OuStorageError): pass

class OuStorage(object):

    def __init__(self):
        self.sd_root = "/sd2"
        self.obs_dir = "/sd2/data/co2temp"

        _logger.debug("Initializing SPI SD card...")
        self.spi = SPI(0, mode=SPI.MASTER)
        SD_CS = Pin('P12')
        try:
            self.sd = sdcard.SDCard(self.spi, SD_CS)
        except OSError as e:
            if "no sd card" in str(e).lower():
                raise NoSdCardError(e)
            else:
                raise

        try:
            flaky.retry_call( os.mount, self.sd, self.sd_root )
        except OSError as e:
            raise SdMountError(e)

        _logger.debug("SD card mounted at %s", self.sd_root)
        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug("ls %s: %s", self.sd_root, os.listdir(self.sd_root))

    def ensure_needed_dirs(self):
        _logger.debug("Ensuring observation dir exists %s", self.obs_dir)
        created_dirs = fileutil.mkdirs(self.obs_dir)
        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug("ls %s: %s", self.obs_dir, os.listdir(self.obs_dir))

    def record_reading(self, reading):
        (YY, MM, DD, hh, mm, ss, _, _) = reading["rtime"]
        row = {}
        row["date"] = "{:04}-{:02}-{:02}".format(YY,MM,DD)
        row["time"] = "{:02}:{:02}:{:02}".format(hh,mm,ss)
        row["co2"] = reading["co2"]
        row["ext_t"] = reading["ext_t"]
        row = "{date}\t{time}\t{co2}\t{ext_t}".format(**row)
        _logger.debug("Data row: %s", row)

        pathparts = [self.sd_root, "data", "co2temp"]
        filename = "{:04}-{:02}.tsv".format(YY, MM)

        path = self.obs_dir + "/" + filename

        _logger.debug("Writing data to %s ...", path)
        with open(path, "at") as f:
            f.write(row)
            f.write("\n")
        _logger.debug("Wrote   data to %s", path)
        _logger.info("%s: %s\t| raw reading: %s", path, row, reading)
        return (path, row)
