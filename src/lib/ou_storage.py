import os

from machine import Pin
from machine import SPI
from machine import SD

import logging
import sdcard

import fileutil

_logger = logging.getLogger("ou_storage")

class OuStorage(object):

    def __init__(self):
        self.sd_root = "/sd2"
        self.obs_dir = "/sd2/data/co2temp"

        _logger.info("Initializing SPI SD card...")
        self.spi = SPI(0, mode=SPI.MASTER)
        SD_CS = Pin('P12')
        self.sd = sdcard.SDCard(self.spi, SD_CS)
        os.mount(self.sd, self.sd_root)
        _logger.info("SD card mounted at %s", self.sd_root)
        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug("ls %s: %s", self.sd_root, os.listdir(self.sd_root))

        _logger.info("Ensuring observation dir exists %s", self.obs_dir)
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

        pathparts = [self.sd_root, "data", "co2temp"]
        filename = "{:04}-{:02}.tsv".format(YY, MM)

        path = self.obs_dir + "/" + filename

        _logger.info("Writing data to %s ...", path)
        with open(path, "at") as f:
            f.write(row)
            f.write("\n")
        _logger.info("Written: %s", row)
