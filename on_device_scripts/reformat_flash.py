import machine
machine.WDT(timeout=1000*60*60*24)

import os
os.mkfs("/flash")

print("Flash FS reformatted")
print("os.listdir('/flash'):", os.listdir("/flash"))
