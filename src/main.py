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

Note that the hw variable does not actually touch the hardware unless we start
accessing its members.
"""

hw = None

try:
    import machine
    wdt = machine.WDT(timeout=10*1000)

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
    # next_state = co2unit_main.STATE_QUICK_HW_TEST
    # next_state = co2unit_main.STATE_COMMUNICATE
    # next_state = co2unit_main.STATE_SCHEDULE
    # raise Exception("Dummy Exception")
    # --------------------------------------------------

    sleep_ms = co2unit_main.run(hw, next_state)

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
    import sys
    import time

    print("Caught exception at top level")
    sys.print_exception(e)

    # Extend watchdog timer in case the user does a KeyboardInterrupt
    wdt = machine.WDT(timeout=30*60*1000)

    try:
        print("Sleeping in ", end="")
        for i in reversed(range(0, 10)):
            print(i+1, end="")
            print(" ", end="")
            for _ in range(0, 10):
                time.sleep_ms(100)
    finally:
        print()

    if hw: hw.prepare_for_shutdown()

    print("Sleeping...")
    machine.deepsleep(5 * 60 * 1000)

except KeyboardInterrupt as e:
    import sys
    sys.print_exception(e)
    print("Caught KeyboardInterrupt. Extending WDT and exiting to REPL...")
    wdt = machine.WDT(timeout=30*60*1000)
