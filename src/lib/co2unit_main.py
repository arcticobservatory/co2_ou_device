import machine
import pycom
import time

import logging
_logger = logging.getLogger("co2unit_main")

import co2unit_hw

# Normal operation
STATE_UNKNOWN           = const(0)
STATE_SELF_TEST         = const(1)
STATE_TAKE_MEASUREMENT  = const(2)

MEASURE_FREQ_MINUTES = 5

def next_state_on_boot(next_state=None):
    if next_state==None:
        try: return pycom.nvs_get("co2_next")
        except: return None
    else:
        pycom.nvs_set("co2_next", next_state)

def run(hw, force_state=None, hw_test_only=False):

    try:
        # Determine next state
        # --------------------------------------------------

        reset_cause = machine.reset_cause()
        wake_reason = machine.wake_reason()
        next_state_hint = next_state_on_boot()

        _logger.info("Start conditions: reset_cause 0x%02x; wake_reason %s; next_state_hint %s; force_state %s;",
                reset_cause, wake_reason, next_state_hint, force_state)

        # Specific reset causes:
        # PWRON_RESET: fresh power on, reset button
        # DEEPSLEEP_RESET: waking from deep sleep
        # WDT_RESET: watchdog timer or machine.reset() in script
        # SOFT_RESET: ctrl+D in REPL
        #
        # Undocumented:
        # SW_CPU_RESET (0xc): core dump crash

        if force_state:
            next_state = force_state

        elif reset_cause == machine.PWRON_RESET:
            _logger.info("Power-on reset")
            next_state = STATE_SELF_TEST

        elif reset_cause == machine.DEEPSLEEP_RESET:
            _logger.info("Woke from deep sleep")
            next_state = STATE_TAKE_MEASUREMENT

        elif reset_cause in [machine.SOFT_RESET, machine.WDT_RESET]:
            _logger.info("Soft reset or self-reset")
            next_state = next_state_hint

        else:
            _logger.warning("Unexpected start conditions")

        if not next_state:
            _logger.warning("No next state determined. Falling back to default...")
            next_state = STATE_TAKE_MEASUREMENT

        next_state_on_boot(STATE_UNKNOWN)

        # Run chosen state
        # --------------------------------------------------

        # Turn on peripherals
        hw.power_peripherals(True)

        if next_state == STATE_SELF_TEST:
            _logger.info("Starting quick self test...")

            # Reset heartbeat to initialize RGB LED, for test feedback
            pycom.heartbeat(True)
            pycom.heartbeat(False)

            # Do self-test
            import co2unit_self_test
            co2unit_self_test.quick_test_hw(hw)

            # If SD card is OK, mount it
            if not co2unit_self_test.failures & co2unit_self_test.FLAG_SD_CARD:
                import os
                os.mount(hw.sdcard(), hw.SDCARD_MOUNT_POINT)

            # Pause to give user a chance to interrupt
            pycom.rgbled(0x222222)
            _logger.info("Pausing before continuing. If you want to interrupt, now is a good time.")
            try:
                for _ in range(0, 50):
                    time.sleep_ms(100)
            except KeyboardInterrupt:
                _logger.info("Caught interrupt. Exiting to REPL")
                pycom.rgbled(0x0)
                import sys
                sys.exit()
            pycom.rgbled(0x0)

            if not hw_test_only:

                # If SD card is OK, check for updates
                if not co2unit_self_test.failures & co2unit_self_test.FLAG_SD_CARD:
                    import co2unit_update
                    updates_dir = hw.SDCARD_MOUNT_POINT + "/updates"
                    updates_installed = co2unit_update.check_and_install_updates(updates_dir)

                    if updates_installed:
                        # Reboot and restart self test
                        next_state_on_boot(STATE_SELF_TEST)
                        machine.reset()

                # Continue with self test
                co2unit_self_test.test_lte_ntp(hw)

            # Set persistent settings
            pycom.wifi_on_boot(False)
            pycom.lte_modem_en_on_boot(False)
            pycom.wdt_on_boot(False)
            pycom.heartbeat_on_boot(False)

        elif next_state == STATE_TAKE_MEASUREMENT:
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
