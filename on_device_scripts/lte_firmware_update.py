"""
Important: ampy run waits for the entire script to finish before giving you output.

For a long-running script like this upgrade, it's important to pass --no-output
to ampy so that ampy exits without waiting for output.
Then you can immediately connect with tio to watch the progress.
"""

# Firmware locations
fw_dir = "/sd/CATM1-41065"
dupname = 'CATM1-41065.dup'
updatername = 'updater.elf'

duppath = "{}/{}".format(fw_dir, dupname)

print("Firmware update script")
print("Expecting firmware on SD card at:", duppath)
print()

import sqnsupgrade
import os
import sys

print("Mounting SD card...")

# Mount SD card on co2unit
import co2unit_hw
hw = co2unit_hw.Co2UnitHw()
hw.mount_sd_card()

# Mount SD card in PyMakr or similar, using default SPI bus
#import machine
#os.mount(machine.SD(), "/sd")

print()

try:
    stat = os.stat(duppath)
except OSError:
    print("Firmware not found. Expected", duppath)
    sys.exit()

print("Firmware found:", duppath, stat)
print()
print("Performing upgrade...", flush=True)
print()
os.chdir(fw_dir)
sqnsupgrade.run(dupname, updatername, debug=True)

# Presumably the script was started with ampy, disconnected,
# and then reconnected with an active tty.
# In that case, explicitly exit
# to ensure we exit to the REPL instead of stalling
# where ampy would normally wait for the end of output.
sys.exit(0)
