import time

import machine

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
        for _ in range(1, 30): time.sleep(1)

#simple_read_loop()

def simple_autonomous():

    try:
        storage = ou_storage.OuStorage()

        rtc = ou_rtc.OuRtc()
        rtc.compare_and_adjust()
        if not ou_rtc.time_reasonable():

            comm = ou_comm.OuComm()
            comm.lte_connect()

            rtc.set_from_ntp()

            #comm.send_test_msg()
            comm.lte_disconnect()

        sensors = ou_sensors.OuSensors()

        while True:

            reading = sensors.take_reading()
            (path, row) = storage.record_reading(reading)
            logging.info("Pause before deep sleep (interrupt now if you need to)")
            for _ in range(1, 5): time.sleep(1)
            logging.info("Going into deep sleep")
            machine.deepsleep(20 * 1000)

    except Exception as e:
        #raise
        logging.info("Restarting soon after unexpected error. %s: %s",
                type(e).__name__, e)
        for _ in range(1, 10): time.sleep(1)
        logging.info("Restarting")
        machine.reset()

simple_autonomous()

# TO CONFIGURE
#
# - Time zone
# - Adapt NTP lib code to adjust timeout, pre-specify IP address?
