import machine
import time

import logging
_logger = logging.getLogger("co2unit_main")

import co2unit_hw

STATE_REPL      = const(1 << 0)
STATE_SELF_TEST = const(1 << 1)
STATE_MEASURE   = const(1 << 2)

MEASURE_FREQ_MINUTES = 5

def next_even_minutes(minutes_divisor):
    tt = time.gmtime()
    minutes = tt[4]
    next_minutes = ((minutes // minutes_divisor) + 1) * minutes_divisor
    # time.mktime() will handle minutes overflow as you would expect:
    # 14:70 -> 15:10
    next_tt = tt[0:4] + (next_minutes, 0, 0, 0)
    return next_tt

def seconds_until_time(next_tt):
    now = time.time()
    secs = time.mktime(next_tt) - now
    return secs

def seconds_until_next_measure():
    measure_time = next_even_minutes(MEASURE_FREQ_MINUTES)
    seconds_left = seconds_until_time(measure_time)
    _logger.info("Next measurement at %s (T minus %d seconds)", measure_time, seconds_left)
    return seconds_left

def determine_next_state_after_reset(reset_cause, wake_reason, prev_state):

    # Specific reset causes:
    # PWRON_RESET: fresh power on, reset button
    # DEEPSLEEP_RESET: waking from deep sleep
    # WDT_RESET: machine.reset() in script
    # SOFT_RESET: ctrl+D in REPL
    #
    # Undocumented:
    # SW_CPU_RESET (0xc): core dump crash

    if reset_cause in [machine.PWRON_RESET, machine.SOFT_RESET]:
        _logger.info("Manual reset (0x%02x). Next step: STATE_SELF_TEST", reset_cause)
        return STATE_SELF_TEST

    elif reset_cause == machine.DEEPSLEEP_RESET:
        _logger.info("Deep sleep reset (0x%02x). Next step: STATE_MEASURE", reset_cause)
        return STATE_MEASURE

    else:
        _logger.warning("Unexpected reset cause (0x%02x)", reset_cause)
        return STATE_SELF_TEST

def run(hw, next_state_override=None):

    try:
        # Turn on peripherals
        hw.power_peripherals(True)

        reset_cause = machine.reset_cause()
        wake_reason = machine.wake_reason()

        next_state = next_state_override \
                or determine_next_state_after_reset(reset_cause, wake_reason, None)

        if next_state == STATE_REPL:
            _logger.info("Exiting to REPL...")
            import sys
            sys.exit()

        elif next_state == STATE_SELF_TEST:
            _logger.info("Starting self-test and full boot sequence...")

            # Reset heartbeat to initialize RGB LED, for test feedback
            import pycom
            pycom.heartbeat(True)
            pycom.heartbeat(False)

            # Do self-test
            import co2unit_self_test
            co2unit_self_test.full_self_test(hw)

            # Turn off all boot options to save power
            pycom.wifi_on_boot(False)
            pycom.lte_modem_en_on_boot(False)
            pycom.wdt_on_boot(False)
            pycom.heartbeat_on_boot(False)

        elif next_state == STATE_MEASURE:
            _logger.info("Starting measurement sequence...")

            try:
                hw.sync_to_most_reliable_rtc()
            except Exception as e:
                _logger.warning("%s: %s", type(e).__name__, e)

            import co2unit_measure
            reading = co2unit_measure.read_sensors(hw)
            _logger.info("Reading: %s", reading)

            import os
            os.mount(hw.sdcard(), hw.SDCARD_MOUNT_POINT)

            reading_data_dir = hw.SDCARD_MOUNT_POINT + "/data/readings"
            co2unit_measure.store_reading(reading, reading_data_dir)

    #except Exception as e:
        # TODO: catch any exception
    finally: pass

    try:
        hw.power_peripherals(False)
        _logger.info("Peripherals off")
    except Exception(e):
        _logger.error("Could not turn off peripherals before sleep. %s: %s", type(e).__name__, e)

    seconds_until_measure = seconds_until_next_measure()
    _logger.info("Sleeping until next measurement (%d sec)", seconds_until_measure)
    machine.deepsleep(seconds_until_measure * 1000)

    # MicroPython does not resume after deep sleep.
    # Function will never return.
    # Machine will reboot after sleep.
