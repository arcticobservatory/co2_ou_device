import machine
machine.WDT(timeout=1000*60*60*24)
print("Current WDT extended to 24 hours")

import pycom
pycom.wdt_on_boot_timeout(1000*60*60*24)
pycom.wdt_on_boot(False)
print("WDT on boot reset to False")
