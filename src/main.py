
try:
    # Configure logging
    import logging
    logging.basicConfig(level=logging.INFO)
    _logger = logging.getLogger("main")

    import time
    import machine
    reset_cause = machine.reset_cause()
    wake_reason = machine.wake_reason()

    # Initialize hardware
    import co2unit_hw
    hw = co2unit_hw.Co2UnitHw()
    hw.power_peripherals(True)

    # If running on the breadboard unit or switching units,
    #   remember to set pinset from REPL...
    # co2unit_hw.pinset_on_boot(co2unit_hw.PINSET_BREADBOARD)
    # co2unit_hw.pinset_on_boot(co2unit_hw.PINSET_PRODUCTION)

    # Special testing zone
    # --------------------------------------------------
    # --------------------------------------------------

    # Determine state and run
    import co2unit_main
    try:
        next_state = co2unit_main.determine_next_state_after_reset(reset_cause, wake_reason, None)
        co2unit_main.run(next_state, hw)

    #except Exception as e:
        # TODO: catch any exception

    finally:
        seconds_until_measure = co2unit_main.seconds_until_next_measure()
        _logger.info("Sleeping until next measurement (%d sec)", seconds_until_measure)
        hw.power_peripherals(False)
        machine.deepsleep(seconds_until_measure * 1000)

finally:
    # TODO: Catch any exception
    pass
