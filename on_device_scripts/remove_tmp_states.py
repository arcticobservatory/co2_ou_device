import os
import sys

# Mount SD card on co2unit
import co2unit_hw
import time
hw = co2unit_hw.Co2UnitHw()
hw.power_peripherals(True)
# Trying to access the SD card too quickly often results in IO errors
print("Giving hardware a moment after power on")
time.sleep_ms(100)
hw.mount_sd_card()

import fileutil
fileutil.rm_recursive("/sd/var")
fileutil.rm_recursive("/sd/updates")
