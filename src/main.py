try:
    # Get handle to hardware
    import co2unit_hw
    hw = co2unit_hw.Co2UnitHw()

    # If running on the breadboard unit or if switching units,
    #   remember to set pinset from REPL...
    # co2unit_hw.pinset_on_boot(co2unit_hw.PINSET_BREADBOARD)
    # co2unit_hw.pinset_on_boot(co2unit_hw.PINSET_PRODUCTION)

    # Defer to co2unit_main
    import co2unit_main

    # Special testing zone
    # --------------------------------------------------
    force_mode = None
    #force_mode = co2unit_main.STATE_EXIT_TO_REPL
    #force_mode = co2unit_main.STATE_HW_TEST_ONLY

    #force_mode = co2unit_main.STATE_TAKE_MEASUREMENT
    #co2unit_main.run(hw, force_mode, exit_to_repl_after=True)
    # --------------------------------------------------

    co2unit_main.run(hw)

#except Exception as e:
    # TODO: Catch any exception
finally: pass
