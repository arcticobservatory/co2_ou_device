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


# Init external RTC
# # https://docs.pycom.io/firmwareapi/pycom/machine/i2c.html
ertc = DS3231(0, pins=('P22','P21'))

# Init external SD card
# # https://docs.pycom.io/firmwareapi/pycom/machine/spi.html
SD_CS = Pin('P12')
spi = SPI(0, mode=SPI.MASTER)

sd = sdcard.SDCard(spi, SD_CS)
os.mount(sd, '/sd2')
print(os.listdir('/sd2'))

# Init external temperature sensor
# https://docs.pycom.io/tutorials/all/owd.html
ow = OneWire(Pin('P3'))
ext_temp = DS18X20(ow)

# Init flash detector diode
# # https://docs.pycom.io/firmwareapi/pycom/machine/pin.html

def pin_handler(arg):
    print("pin change")

flash_pin = Pin('P4', mode=Pin.IN, pull=Pin.PULL_UP)
flash_pin.callback(Pin.IRQ_FALLING, pin_handler)


def take_reading():

    # Start temperature reading
    ext_temp.start_conversion()
    ext_t_start_ticks = time.ticks_ms()

    # Wait for temperature reading
    # Temperature reading seems to take around 650 ms (datasheet says under 750 ms)
    while True:
        ext_t_reading = ext_temp.read_temp_async()
        if ext_t_reading != None:
            ext_t_ticks = time.ticks_diff(ext_t_start_ticks, time.ticks_ms())
            break
        time.sleep_ms(1)


    # Read flash sensor
    flash_reading = flash_pin()

    # Read RTC
    time = ertc.get_time(True)

    return {
            "time": read_time,
            "ext_t": ext_t_reading,
            "ext_t_ms": ext_t_ticks,
            "flash": flash_reading,
            }

while True:

    reading = take_reading()
    print(reading)
    time.sleep(5)
