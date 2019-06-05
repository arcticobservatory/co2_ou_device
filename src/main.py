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

def isotime(mktime_tuple):
    (YY, MM, DD, hh, mm, ss, wday, yday) = mktime_tuple
    return "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}".format(YY, MM, DD, hh, mm, ss)

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

    def init_rtc(self):
        with TaskContext("Init RTC"):
            # Init external RTC
            # # https://docs.pycom.io/firmwareapi/pycom/machine/i2c.html
            self.ertc = DS3231(0, pins=('P22','P21'))
        print("\tTime:", self.ertc.get_time())

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
            os.mount(self.sd, '/sd2')
        print("\tContents:", os.listdir('/sd2'))

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
        wtime_tuple = self.ertc.get_time(True)
        wtime_ts = time.mktime(wtime_tuple)
        wtime_iso = isotime(wtime_tuple)

        return {
                "wtime_tuple": wtime_tuple,
                "wtime_ts": wtime_ts,
                "wtime_iso": wtime_iso,
                "co2": None,
                "ext_t": ext_t_reading,
                "ext_t_ms": ext_t_ticks,
                "flash": flash_reading,
                }

    def record_reading(self, reading):
        filename = reading["wtime_iso"][0:7] + ".tsv"
        pathparts = ["/sd2", "data", "co2temp"]

        for i in range(2, len(pathparts)+1):
            curpath = "/".join(pathparts[0:i])
            print("{:39} ".format("Directory " + curpath), end="")
            try:
                os.mkdir(curpath)
                print("Created")
            except OSError as e:
                if "file exists" in str(e): print("Exists")
                else: print("Fail"); raise e

        path = "/".join(pathparts + [filename])
        with TaskContext("Recording reading to "+path):
            with open(path, "at") as f:
                row = "{wtime_iso}\t{co2}\t{ext_t}\n".format(**reading)
                f.write(row)
        print(row, end="")


co2unit = Co2Unit()
co2unit.init_rtc()
co2unit.init_sensors()
co2unit.init_storage()

while True:

    reading = co2unit.take_reading()
    co2unit.record_reading(reading)
    print(reading)
    time.sleep(5)
