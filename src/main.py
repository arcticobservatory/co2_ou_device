import time

import logging

from ou_rtc import OuRtc
from ou_sensors import OuSensors
from ou_storage import OuStorage

logging.basicConfig(level=logging.DEBUG)

def simple_read_loop():

    ou_rtc = OuRtc()
    ou_sensors = OuSensors()
    ou_storage = OuStorage()

    while True:

        rtime = time.now()
        reading = ou_sensors.take_reading()
        reading["rtime"] = rtime
        (path, row) = ou_storage.record_reading(reading)
        logging.info("%s: %s\t| raw reading: %s", path, row, reading)

        logging.debug("Going into light sleep")
        time.sleep(5)
        logging.debug("Woke up")

#simple_read_loop()

#from ou_comm import OuComm
#ou_comm = OuComm()
#ou_comm.run()

ou_rtc = OuRtc()
ou_rtc.compare_and_adjust()

from ou_comm import OuComm
ou_comm = OuComm()
ou_comm.lte_connect()
ou_rtc.set_from_ntp()
#ou_comm.send_test_msg()
#ou_comm.lte_disconnect()

#simple_read_loop()


# TO CONFIGURE
#
# - Time zone
# - NTP IP address?
