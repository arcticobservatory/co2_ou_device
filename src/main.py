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
    WDT_TIMEOUT_DEFAULT     = const(1000*10)
    WDT_TIMEOUT_REPL        = const(1000*60*30)
    ERROR_SLEEP_MS_DEFAULT  = const(1000*60*15)

    import machine
    wdt = machine.WDT(timeout=WDT_TIMEOUT_DEFAULT)

    import sys
    import time

    import co2unit_id
    print("co2unit hardware id:", co2unit_id.hardware_id())

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
    # next_state = co2unit_main.STATE_MEASURE
    # co2unit_main.run(hw, next_state)
    # exit_to_repl_after = True
    # next_state = co2unit_main.STATE_QUICK_HW_TEST
    # next_state = co2unit_main.STATE_COMMUNICATE
    # next_state = co2unit_main.STATE_SCHEDULE
    # next_state = co2unit_main.STATE_MEASURE
    # next_state = co2unit_main.STATE_RECORD_FLASH
    # raise Exception("Dummy Exception")
    # --------------------------------------------------

    sleep_ms, next_state = co2unit_main.run(hw, next_state)
    co2unit_main.next_state_on_boot(next_state)

    if exit_to_repl_after:
        wdt = machine.WDT(timeout=WDT_TIMEOUT_REPL)
        sys.exit()

    hw.prepare_for_shutdown()
    if not sleep_ms:
        print("Resetting...")
        time.sleep_ms(20)    # Give a moment for output buffer to flush
        machine.reset()
    else:
        print("Sleeping...")
        machine.deepsleep(sleep_ms)

except Exception as e:
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
        wdt = machine.WDT(timeout=WDT_TIMEOUT_REPL)
        sys.exit()

    # Determine how long to sleep
    try:
        # Attempt to return to normal schedule
        import co2unit_main
        sleep_ms, next_state = co2unit_main.schedule_wake(hw)
        co2unit_main.next_state_on_boot(next_state)
    except Exception as e2:
        print("Error trying to schedule wakeup...")
        sys.print_exception(e2)
        sleep_ms = ERROR_SLEEP_MS_DEFAULT
        print("Falling back to default", sleep_ms, "ms")

    try:
        hw.prepare_for_shutdown()
    except Exception as e2:
        print("Error trying to prepare for shutdown...")
        sys.print_exception(e2)

    print("Sleeping...")
    machine.deepsleep(sleep_ms)

except KeyboardInterrupt as e:
    sys.print_exception(e)
    print("Caught KeyboardInterrupt. Extending WDT and exiting to REPL...")
    wdt = machine.WDT(timeout=WDT_TIMEOUT_REPL)
    sys.exit()
