import time
import os
import sdcard

from machine import I2C
from machine import SPI
from onewire import DS18X20
from onewire import OneWire
from machine import Pin

from machine import SD
from ds3231 import DS3231

def pin_handler(arg):
    print("pin change")


# # https://docs.pycom.io/firmwareapi/pycom/machine/i2c.html

ertc = DS3231(0, pins=('P22','P21'))

print(ertc.get_time(True))

# # rtc code


# # https://docs.pycom.io/firmwareapi/pycom/machine/spi.html
SD_CS = Pin('P12')
spi = SPI(0, mode=SPI.MASTER)

sd = sdcard.SDCard(spi, SD_CS)
os.mount(sd, '/sd2')
print(os.listdir('/sd2'))

# # sd code

# https://docs.pycom.io/tutorials/all/owd.html
ow = OneWire(Pin('P3'))
temp = DS18X20(ow)




# temp code

# # https://docs.pycom.io/firmwareapi/pycom/machine/pin.html
flash_pin = Pin('P4', mode=Pin.IN, pull=Pin.PULL_UP)
flash_pin.callback(Pin.IRQ_FALLING, pin_handler)







while True:
    print(temp.read_temp_async())
    time.sleep(1)
    temp.start_conversion()
    time.sleep(1)
    print("flash: " + str(flash_pin()))