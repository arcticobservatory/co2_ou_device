import time
import os
import sdcard
import machine

from machine import I2C
from machine import SPI
from onewire import DS18X20
from onewire import OneWire
from machine import Pin

from machine import SD
from ds3231 import DS3231

import fileutil

class TaskContext(object):
    def __init__(self, desc):
        self.desc = desc

    def __enter__(self):
        print("{:39} ".format(self.desc), end="")

    def __exit__(self, exc_type, exc_value, traceback):
        if not exc_type:
            print("OK")
        else:
            print("Fail")

class Co2Unit(object):

    def __init__(self):
        self.sd_root = "/sd2"
        self.obs_dir = "/sd2/data/co2temp"

    def init_rtc(self):
        with TaskContext("Init RTC"):
            # Init external RTC
            # # https://docs.pycom.io/firmwareapi/pycom/machine/i2c.html
            self.ertc = DS3231(0, pins=('P22','P21'))
        print("Time:", self.ertc.get_time())

    def init_sensors(self):
        with TaskContext("Init external temperature sensor"):
            # https://docs.pycom.io/tutorials/all/owd.html
            ow = OneWire(Pin('P3'))
            self.ext_temp = DS18X20(ow)

        with TaskContext("Init flash pin"):
            # # https://docs.pycom.io/firmwareapi/pycom/machine/pin.html
            self.flash_pin = Pin('P4', mode=Pin.IN, pull=Pin.PULL_UP)
            self.flash_pin.callback(Pin.IRQ_FALLING, self.on_flash_pin)

    def init_storage(self):
        with TaskContext("Init SD card"):
            # # https://docs.pycom.io/firmwareapi/pycom/machine/spi.html
            self.spi = SPI(0, mode=SPI.MASTER)
            SD_CS = Pin('P12')
            self.sd = sdcard.SDCard(self.spi, SD_CS)
            os.mount(self.sd, self.sd_root)
        print("Root dir:", os.listdir(self.sd_root))

        with TaskContext("Ensure observation dir exists"):
            created_dirs = fileutil.mkdirs(self.obs_dir)
        for d in created_dirs:
            print("Created", d)
        print("Obs dir:", os.listdir(self.obs_dir))

    def on_flash_pin(self, arg):
        print("pin change")

    def take_reading(self):

        # Start temperature reading
        self.ext_temp.start_conversion()
        ext_t_start_ticks = time.ticks_ms()

        # Wait for temperature reading
        # Temperature reading seems to take around 650 ms (datasheet says under 750 ms)
        while True:
            ext_t_reading = self.ext_temp.read_temp_async()
            if ext_t_reading != None:
                ext_t_ticks = time.ticks_diff(ext_t_start_ticks, time.ticks_ms())
                break
            time.sleep_ms(1)

        # Read flash sensor
        flash_reading = self.flash_pin()

        # Read RTC
        rtime = self.ertc.get_time(True)

        return {
                "rtime": rtime,
                "co2": None,
                "ext_t": ext_t_reading,
                "ext_t_ms": ext_t_ticks,
                "flash": flash_reading,
                }

    def record_reading(self, reading):
        (YY, MM, DD, hh, mm, ss, _, _) = reading["rtime"]
        row = {}
        row["date"] = "{:04}-{:02}-{:02}".format(YY,MM,DD)
        row["time"] = "{:02}:{:02}:{:02}".format(hh,mm,ss)
        row["co2"] = reading["co2"]
        row["ext_t"] = reading["ext_t"]
        row = "{date}\t{time}\t{co2}\t{ext_t}\n".format(**row)

        pathparts = [self.sd_root, "data", "co2temp"]
        filename = "{:04}-{:02}.tsv".format(YY, MM)

        path = self.obs_dir + "/" + filename
        with TaskContext("Recording to " + path):
            with open(path, "at") as f:
                f.write(row)
        print(row, end="")

    def read_and_record(self):
        print()
        with TaskContext("Reading sensors"):
            reading = self.take_reading()
        print(reading)
        self.record_reading(reading)

co2unit = Co2Unit()
co2unit.init_rtc()
co2unit.init_sensors()
co2unit.init_storage()

while True:

    co2unit.read_and_record()
    time.sleep(5)
