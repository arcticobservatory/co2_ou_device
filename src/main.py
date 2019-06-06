import time

from ds3231 import DS3231
import logging

from ou_storage import OuStorage
from ou_sensors import OuSensors

logging.basicConfig(level=logging.DEBUG)

ertc = DS3231(0, pins=('P22','P21'))
ou_sensors = OuSensors()
ou_storage = OuStorage()

while True:

    print()
    rtime = ertc.get_time(True)
    reading = ou_sensors.take_reading()
    reading["rtime"] = rtime
    ou_storage.record_reading(reading)

    logging.info("Going into light sleep")
    time.sleep(5)
