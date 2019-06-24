
class SetupIncompleteError(Exception): pass

try:
    # Configure logging
    import logging
    logging.basicConfig(level=logging.INFO)

    import machine
    reset_cause = machine.reset_cause()
    wake_reason = machine.wake_reason()

    # Specific reset causes:
    # PWRON_RESET: fresh power on, reset button
    # DEEPSLEEP_RESET: waking from deep sleep
    # WDT_RESET: machine.reset() in script
    # SOFT_RESET: ctrl+D in REPL

    if reset_cause in [machine.PWRON_RESET, machine.SOFT_RESET]:
        logging.info("Manual reset (0x%02x). Starting self-test and full boot sequence...", reset_cause)

        # Initialize hardware
        # --------------------------------------------------

        import co2unit_hw
        hw = co2unit_hw.Co2UnitHw()
        hw.power_peripherals(True)

        # If running on the breadboard unit or switching units,
        #   remember to set pinset from REPL...
        # co2unit_hw.pinset_on_boot(co2unit_hw.PINSET_BREADBOARD)
        # co2unit_hw.pinset_on_boot(co2unit_hw.PINSET_PRODUCTION)

        # Do self-test
        # --------------------------------------------------

        import time
        import co2unit_self_test as post

        # Reset heartbeat in initialize RGB LED, for test feedback
        import pycom
        pycom.heartbeat(True)
        pycom.heartbeat(False)

        # First, the quick hardware check
        post.quick_check(hw)
        logging.info("Failures after quick hardware check: {:#018b}".format(post.failures))
        post.display_errors_led()

        # Freeze with light on for fatal errors that require human assistance
        for flag in post.SETUP_INCOMPLETE_FLAGS:
            if post.failures & flag:
                pycom.rgbled(post.flag_color(flag))
                raise SetupIncompleteError("Fatal hardware or firmware error: %s" % post.flag_name(flag))

        # Then the LTE check
        post.test_lte_ntp(hw)
        post.show_boot_flags()
        logging.info("Failures after LTE test: {:#018b}".format(post.failures))
        post.display_errors_led()

        # Do first-time persistent setup
        # --------------------------------------------------

        # Turn off all boot options to save power
        pycom.wifi_on_boot(False)
        pycom.lte_modem_en_on_boot(False)
        pycom.wdt_on_boot(False)
        pycom.heartbeat_on_boot(False)

    elif reset_cause == machine.DEEPSLEEP_RESET:
        logging.info("Reset cause: DEEPSLEEP_RESET (0x%02x)", reset_cause)

    elif reset_cause == machine.WDT_RESET:
        logging.info("Reset cause: WDT_RESET (0x%02x)", reset_cause)

    else:
        logging.info("Unexpected reset cause (0x%02x)", reset_cause)

except SetupIncompleteError as e:
    # These errors indicate that manual setup was not completed.
    # Re-raise to interrupt operation to call for manual intervention.
    raise e

finally:
    # TODO: Catch any exception and go back to sleep
    pass
