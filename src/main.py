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
    force_state = None

    #force_state = co2unit_main.STATE_TAKE_MEASUREMENT
    #co2unit_main.run(hw, force_state, hw_test_only=True)

    import pycom
    pycom.lte_modem_en_on_boot(True)

    import co2unit_comm
    co2unit_comm.hello_server_world()

    import sys
    sys.exit()
    # --------------------------------------------------

    co2unit_main.run(hw)

#except Exception as e:
    # TODO: Catch any exception
finally: pass
