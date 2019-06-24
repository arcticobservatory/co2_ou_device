
try:
    # Configure logging
    import logging
    logging.basicConfig(level=logging.INFO)
    _logger = logging.getLogger("main")

    import machine
    reset_cause = machine.reset_cause()
    wake_reason = machine.wake_reason()

    import time

    # Specific reset causes:
    # PWRON_RESET: fresh power on, reset button
    # DEEPSLEEP_RESET: waking from deep sleep
    # WDT_RESET: machine.reset() in script
    # SOFT_RESET: ctrl+D in REPL

    if reset_cause in [machine.PWRON_RESET, machine.SOFT_RESET]:
        _logger.info("Manual reset (0x%02x). Starting self-test and full boot sequence...", reset_cause)

        # Initialize hardware
        import co2unit_hw
        hw = co2unit_hw.Co2UnitHw()
        hw.power_peripherals(True)

        # If running on the breadboard unit or switching units,
        #   remember to set pinset from REPL...
        # co2unit_hw.pinset_on_boot(co2unit_hw.PINSET_BREADBOARD)
        # co2unit_hw.pinset_on_boot(co2unit_hw.PINSET_PRODUCTION)

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

    elif reset_cause == machine.DEEPSLEEP_RESET:
        _logger.info("Reset cause: DEEPSLEEP_RESET (0x%02x)", reset_cause)

    elif reset_cause == machine.WDT_RESET:
        _logger.info("Reset cause: WDT_RESET (0x%02x)", reset_cause)

    else:
        _logger.info("Unexpected reset cause (0x%02x)", reset_cause)

finally:
    # TODO: Catch any exception and go back to sleep
    pass
