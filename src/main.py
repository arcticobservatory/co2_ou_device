"""
Top level shell file

This file should contain as little logic as possible.
Its goal is to never lose control of the device into an unrecoverable state (like the REPL).

- The unit should never crash out to the REPL except for a KeyboardInterrupt.
- All other exceptions should result in going back to sleep for a few minutes
  and then trying again.
- In the worst case scenario, the watchdog timer (WDT) will cause a reset.

All allocation and logic should defer to co2unit_main.py.
The exception of this is to set the hw variable to make it easier to work with
if we do exit to the REPL.

Note that the hw object does not actually touch the hardware unless we start
accessing its members.
"""

hw = None
exit_to_repl_after = False

try:
    DEFAULT_WDT_TIMEOUT = const(10*1000)
    REPL_WDT_TIMEOUT    = const(30*60*1000)
    ERROR_SLEEP_MS      = const(5*60*1000)

    import sys
    import machine
    wdt = machine.WDT(timeout=DEFAULT_WDT_TIMEOUT)

    # Get handle to hardware
    import co2unit_hw
    hw = co2unit_hw.Co2UnitHw()

    # If running on the breadboard unit or if switching units,
    #   remember to set pinset from REPL...
    # co2unit_hw.pinset_on_boot(co2unit_hw.PINSET_BREADBOARD)
    # co2unit_hw.pinset_on_boot(co2unit_hw.PINSET_PRODUCTION)

    # Defer to co2unit_main
    import co2unit_main
    next_state = co2unit_main.determine_state_after_reset()

    # Area for temporary test overrides
    # --------------------------------------------------
    # exit_to_repl_after = True
    # next_state = co2unit_main.STATE_QUICK_HW_TEST
    # next_state = co2unit_main.STATE_COMMUNICATE
    # next_state = co2unit_main.STATE_SCHEDULE
    # next_state = co2unit_main.STATE_TAKE_MEASUREMENT
    # raise Exception("Dummy Exception")
    # --------------------------------------------------

    sleep_ms = co2unit_main.run(hw, next_state)

    if exit_to_repl_after:
        wdt = machine.WDT(timeout=REPL_WDT_TIMEOUT)
        sys.exit()

    hw.prepare_for_shutdown()
    if not sleep_ms:
        import time
        print("Resetting...")
        time.sleep_ms(5)    # Give a moment for output buffer to flush
        machine.reset()
    else:
        print("Sleeping...")
        machine.deepsleep(sleep_ms)

except Exception as e:
    import time

    # Show exception
    print("Caught exception at top level")
    sys.print_exception(e)

    # Attempt to record exception
    try:
        import co2unit_errors
        co2unit_errors.record_error(hw, e, "Uncaught exception at top level")
    except Exception as e2:
        print("Error trying to record first exception...")
        sys.print_exception(e2)

    if exit_to_repl_after:
        wdt = machine.WDT(timeout=REPL_WDT_TIMEOUT)
        sys.exit()

    try:
        hw.prepare_for_shutdown()
    except Exception as e2:
        print("Error trying to prepare for shutdown...")
        sys.print_exception(e2)

    print("Sleeping...")
    machine.deepsleep(ERROR_SLEEP_MS)

except KeyboardInterrupt as e:
    sys.print_exception(e)
    print("Caught KeyboardInterrupt. Extending WDT and exiting to REPL...")
    wdt = machine.WDT(timeout=REPL_WDT_TIMEOUT)
    sys.exit()
