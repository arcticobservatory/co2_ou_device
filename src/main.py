import time

import logging

import ou_comm
import ou_rtc
import ou_sensors
import ou_storage

logging.basicConfig(level=logging.INFO)

def simple_read_loop():

    rtc = ou_rtc.OuRtc()
    sensors = ou_sensors.OuSensors()
    storage = ou_storage.OuStorage()

    while True:

        reading = sensors.take_reading()
        (path, row) = storage.record_reading(reading)
        logging.info("%s: %s\t| raw reading: %s", path, row, reading)

        logging.debug("Going into light sleep")
        for _ in range(1, 30): time.sleep(1)

#simple_read_loop()

def connect_set_time_and_run():

    rtc = ou_rtc.OuRtc()
    rtc.compare_and_adjust()

    try:
        comm = ou_comm.OuComm()
        comm.lte_connect()

        rtc.set_from_ntp()

        #comm.send_test_msg()
        #comm.lte_disconnect()

        simple_read_loop()

    except Exception as e:
        raise
        logging.info("Restarting soon after unexpected error. %s: %s",
                type(e).__name__, e)
        for _ in range(1, 10): time.sleep(1)
        logging.info("Restarting")
        import machine
        machine.reset()

connect_set_time_and_run()

# TO CONFIGURE
#
# - Time zone
# - Adapt NTP lib code to adjust timeout, pre-specify IP address?
