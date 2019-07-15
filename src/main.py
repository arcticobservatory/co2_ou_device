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

try:
    import machine
    wdt = machine.WDT(timeout=5*60*1000)

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

    #force_state = co2unit_main.STATE_COMMUNICATE
    #co2unit_main.run(hw, force_state, hw_test_only=True)
    # --------------------------------------------------

    co2unit_main.run(hw)

except Exception as e:
    import sys
    import time

    sys.print_exception(e)
    print("Caught exception at top level. Waiting a moment for interrupt before deep sleep.")
    time.sleep(5)
    print("Sleeping...")
    machine.deepsleep(5 * 60 * 1000)

except KeyboardInterrupt as e:
    import sys
    import machine

    sys.print_exception(e)
    print("Caught KeyboardInterrupt. Extending WDT and exiting to REPL...")
    wdt = machine.WDT(timeout=30*60*1000)
