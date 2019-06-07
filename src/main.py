import time

import logging

from ou_rtc import OuRtc
from ou_sensors import OuSensors
from ou_storage import OuStorage, SdInitError

logging.basicConfig(level=logging.DEBUG)

def simple_read_loop():

    ou_rtc = OuRtc()
    ou_sensors = OuSensors()
    ou_storage = OuStorage()

    while True:

        rtime = time.gmtime()
        reading = ou_sensors.take_reading()
        reading["rtime"] = rtime
        (path, row) = ou_storage.record_reading(reading)
        logging.info("%s: %s\t| raw reading: %s", path, row, reading)

        logging.debug("Going into light sleep")
        for _ in range(1, 30): time.sleep(1)

#simple_read_loop()

from ou_comm import OuComm, InitModemError

def connect_and_set_with_ntp():

    ou_rtc = OuRtc()
    ou_rtc.compare_and_adjust()

    try:
        ou_comm = OuComm()
        ou_comm.lte_connect()

        ou_rtc.set_from_ntp()

        #ou_comm.send_test_msg()
        #ou_comm.lte_disconnect()

        simple_read_loop()

    except (InitModemError, TimeoutError) as e:
        logging.info("Restarting soon after unrecoverable error. %s: %s",
                type(e).__name__, e)
        for _ in range(1, 10): time.sleep(1)
        logging.info("Restarting")
        import machine
        machine.reset()

connect_and_set_with_ntp()

# TO CONFIGURE
#
# - Time zone
# - Adapt NTP lib code to adjust timeout, pre-specify IP address?
