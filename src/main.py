import time

import logging

from ou_rtc import OuRtc
from ou_sensors import OuSensors
from ou_storage import OuStorage

logging.basicConfig(level=logging.INFO)

ou_rtc = OuRtc()
ou_sensors = OuSensors()
ou_storage = OuStorage()

while True:

    rtime = ou_rtc.get_time()
    reading = ou_sensors.take_reading()
    reading["rtime"] = rtime
    (path, row) = ou_storage.record_reading(reading)
    logging.info("%s: %s\t| raw reading: %s", path, row, reading)

    logging.debug("Going into light sleep")
    time.sleep(5)
    logging.debug("Woke up")
