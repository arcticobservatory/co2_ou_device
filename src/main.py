
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

        import co2unit_hw
        #co2unit_hw.pinset_on_boot(co2unit_hw.PINSET_BREADBOARD)
        #co2unit_hw.pinset_on_boot(co2unit_hw.PINSET_PRODUCTION)
        hw = co2unit_hw.Co2UnitHw()
        hw.power_peripherals(True)

        # Do self-test
        # --------------------------------------------------

        # Make sure heartbeat is off, because we're going to use the LED
        import pycom
        pycom.heartbeat(False)

        import co2unit_self_test as post

        post.quick_check(hw)
        # If the only failure is that the time source is missing, connect to NTP
        if post.failures == post.FLAG_TIME_SOURCE:
            post.test_lte_ntp(hw)
        post.show_boot_flags()

        logging.info("Self-test failure flags: {:#018b}".format(post.failures))
        post.display_errors_led()

        if post.failures & post.FLAG_LTE_FW_API:
            pycom.rgbled(post.flag_color(post.FLAG_LTE_FW_API))
            raise SetupIncompleteError("Missing LTE API. Need to upgrade Pycom firmware.")

        # Do first-time persistent setup
        # --------------------------------------------------

        pycom.wifi_on_boot(False)
        pycom.lte_modem_en_on_boot(False)
        pycom.wdt_on_boot(False)
        pycom.heartbeat_on_boot(True)

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
