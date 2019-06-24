try:
    # If running on the breadboard unit or if switching units,
    #   remember to set pinset from REPL...
    # co2unit_hw.pinset_on_boot(co2unit_hw.PINSET_BREADBOARD)
    # co2unit_hw.pinset_on_boot(co2unit_hw.PINSET_PRODUCTION)

    # Defer to co2unit_main
    import co2unit_main
    next_state_override = None

    # Special testing zone
    # --------------------------------------------------
    #next_state_override = co2unit_main.STATE_REPL
    # --------------------------------------------------

    co2unit_main.run(next_state_override)

#except Exception as e:
    # TODO: Catch any exception
finally: pass
