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

#import main_old

import co2unit_main2 as main

#raise KeyboardInterrupt()

with main.MainWrapper():

    runner = main.TaskRunner()
    runner.run(main.BootUp)
    raise KeyboardInterrupt()
