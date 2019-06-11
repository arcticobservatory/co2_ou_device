import time

import machine
import pycom

import logging

import ou_comm
import ou_rtc
import ou_sensors
import ou_storage

import ou_post

logging.basicConfig(level=logging.INFO)
#ou_sensors._logger.setLevel(logging.DEBUG)
#ou_rtc._logger.setLevel(logging.DEBUG)

def simple_read_loop():

    rtc = ou_rtc.OuRtc()
    sensors = ou_sensors.OuSensors()
    storage = ou_storage.OuStorage()

    while True:

        reading = sensors.take_reading()
        (path, row) = storage.record_reading(reading)
        for _ in range(1, 30): time.sleep(1)

#simple_read_loop()

def sleep_until_read_time():
    wake_time = ou_rtc.next_even_minutes(5)
    sleep_sec = ou_rtc.seconds_until_time(wake_time)
    logging.info("Sleeping until %s (%d sec)", wake_time, sleep_sec)
    machine.deepsleep(sleep_sec*1000)

def simple_autonomous():

    # When you run machine.reset():
    #   - the boot message shows: rst:0x7 (TG0WDT_SYS_RESET)
    #   - but machine.reset() shows: 2 (machine.WDT_RESET)
    logging.debug("reset_cause %s; post_on_boot %s", machine.reset_cause(), ou_post.post_on_boot())

    if machine.reset_cause() == machine.PWRON_RESET or ou_post.post_on_boot():
        errors = ou_post.do_post()

        if ou_post.errors_need_physical_fix(errors):
            while True: ou_post.show_errors(errors)
        elif ou_post.should_try_reset(errors):
            logging.info("Errors may be fixed with reset. Resetting.")
            ou_post.post_on_boot(True)
            machine.reset()

        ou_post.post_on_boot(False)
        sleep_until_read_time()

    try:
        storage = ou_storage.OuStorage()
        storage.ensure_needed_dirs()

        rtc = ou_rtc.OuRtc()
        rtc.compare_and_adjust()
        if not ou_rtc.time_reasonable():

            comm = ou_comm.OuComm()
            comm.lte_connect()

            rtc.set_from_ntp()

            #comm.send_test_msg()
            comm.lte_disconnect()

        sensors = ou_sensors.OuSensors()

        reading = sensors.take_reading()
        (path, row) = storage.record_reading(reading)

        sleep_until_read_time()

    except ou_comm.InitModemError:
        logging.info("Could not init modem. Restarting and trying again")
        for _ in range(0,10): time.sleep(1)
        machine.reset()

simple_autonomous()

# TO CONFIGURE
#
# - Time zone
# - Adapt NTP lib code to adjust timeout, pre-specify IP address?
