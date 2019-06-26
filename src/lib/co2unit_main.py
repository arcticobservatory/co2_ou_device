import machine
import pycom
import time

import logging
_logger = logging.getLogger("co2unit_main")

import co2unit_hw

# Special testing modes
MODE_EXIT_TO_REPL       = const(1)
MODE_HW_TEST_ONLY       = const(2)

# Normal operation
MODE_FULL_SELF_TEST     = const(3)
MODE_TAKE_MEASUREMENT   = const(4)

MEASURE_FREQ_MINUTES = 5

def determine_mode_after_reset(reset_cause, wake_reason):

    # Specific reset causes:
    # PWRON_RESET: fresh power on, reset button
    # DEEPSLEEP_RESET: waking from deep sleep
    # WDT_RESET: machine.reset() in script
    # SOFT_RESET: ctrl+D in REPL
    #
    # Undocumented:
    # SW_CPU_RESET (0xc): core dump crash

    if reset_cause in [machine.PWRON_RESET, machine.SOFT_RESET]:
        _logger.info("Manual reset (0x%02x). Next step: MODE_FULL_SELF_TEST", reset_cause)
        return MODE_FULL_SELF_TEST

    elif reset_cause == machine.DEEPSLEEP_RESET:
        _logger.info("Deep sleep reset (0x%02x). Next step: MODE_TAKE_MEASUREMENT", reset_cause)
        return MODE_TAKE_MEASUREMENT

    else:
        _logger.warning("Unexpected reset cause (0x%02x)", reset_cause)
        return MODE_FULL_SELF_TEST

def run(hw, force_mode=None, exit_to_repl_after=False):

    try:
        reset_cause = machine.reset_cause()
        wake_reason = machine.wake_reason()

        run_mode = force_mode \
                or determine_mode_after_reset(reset_cause, wake_reason)

        # Turn on peripherals
        hw.power_peripherals(True)

        if run_mode == MODE_EXIT_TO_REPL:
            _logger.info("Exiting to REPL...")
            import sys
            sys.exit()

        elif run_mode == MODE_HW_TEST_ONLY:
            _logger.info("Starting quick self test...")

            # Reset heartbeat to initialize RGB LED, for test feedback
            pycom.heartbeat(True)
            pycom.heartbeat(False)

            # Do self-test
            import co2unit_self_test
            co2unit_self_test.quick_test_hw(hw)

        elif run_mode == MODE_FULL_SELF_TEST:
            _logger.info("Starting self-test and full boot sequence...")

            # Reset heartbeat to initialize RGB LED, for test feedback
            pycom.heartbeat(True)
            pycom.heartbeat(False)

            # Do self-test
            import co2unit_self_test
            co2unit_self_test.quick_test_hw(hw)
            co2unit_self_test.test_lte_ntp(hw)

            # Turn off all boot options to save power
            pycom.wifi_on_boot(False)
            pycom.lte_modem_en_on_boot(False)
            pycom.wdt_on_boot(False)
            pycom.heartbeat_on_boot(False)

        elif run_mode == MODE_TAKE_MEASUREMENT:
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

    if exit_to_repl_after:
        import sys
        sys.exit()

    # Go to sleep until next wake-up
    try:
        hw.power_peripherals(False)
        _logger.info("Peripherals off")
    except Exception(e):
        _logger.error("Could not turn off peripherals before sleep. %s: %s", type(e).__name__, e)

    import timeutil

    measure_time = timeutil.next_even_minutes(MEASURE_FREQ_MINUTES)
    seconds_until_measure = timeutil.seconds_until_time(measure_time)
    _logger.info("Next measurement at %s (T minus %d seconds)", measure_time, seconds_until_measure)
    _logger.info("Sleeping until next measurement (%d sec)", seconds_until_measure)
    machine.deepsleep(seconds_until_measure * 1000)

    # MicroPython does not resume after deep sleep.
    # Function will never return.
    # Machine will reboot after sleep.
