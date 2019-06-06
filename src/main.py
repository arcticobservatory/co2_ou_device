import os
import time

from machine import I2C
from machine import Pin
from onewire import DS18X20
from onewire import OneWire
import machine

from ds3231 import DS3231
import logging
import sdcard

from ou_storage import OuStorage
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
        self.ou_storage = OuStorage()

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
        self.ou_storage.record_reading(reading)

    def read_and_record(self):
        print()
        with TaskContext("Reading sensors"):
            reading = self.take_reading()
        print(reading)
        self.record_reading(reading)

logging.basicConfig(level=logging.DEBUG)

co2unit = Co2Unit()
co2unit.init_rtc()
co2unit.init_sensors()

ou_storage = OuStorage()

while True:

    print()
    with TaskContext("Reading sensors"):
        reading = co2unit.take_reading()
    print(reading)
    ou_storage.record_reading(reading)
    time.sleep(5)
