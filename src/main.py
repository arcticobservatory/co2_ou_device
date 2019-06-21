# Turn off heartbeat
import pycom
pycom.heartbeat(False)

# Configure logging
import logging
logging.basicConfig(level=logging.INFO)

# Do self-test
import co2unit_hw
import co2unit_self_test as post

#co2unit_hw.pinset_on_boot(co2unit_hw.PINSET_BREADBOARD)
#co2unit_hw.pinset_on_boot(co2unit_hw.PINSET_PRODUCTION)

hw = co2unit_hw.Co2UnitHw()
hw.power_peripherals(True)

post.quick_check(hw)
# If the only failure is that the time source is missing, connect to NTP
if post.failures == post.FLAG_TIME_SOURCE:
    post.test_lte_ntp(hw)
post.show_boot_flags()

post._logger.setLevel(logging.DEBUG)
post.display_errors_led()

print("Failure flags: {:#018b}".format(post.failures))

# Updates
import co2unit_update
co2unit_update._logger.setLevel(logging.DEBUG)
import os

co2unit_hw._logger.setLevel(logging.DEBUG)

os.mount(hw.sdcard(), "/sd")
os.chdir("/sd/updates/update-2019-06-13")
appimg = 'firmware-pycom-fipy-1.18.2.r7/appimg.bin'
print()
print("To flash Pycom firmware run:")
print("co2unit_update.do_pycom_ota(appimg)")
print()

dup = "firmware-modem-CATM1-41065/CATM1-41065/CATM1-41065.dup"
elf = "firmware-modem-CATM1-41065/CATM1-41065/updater.elf"
print()
print("To update modem firmware run:")
print("co2unit_update.do_modem_upgrade(dup, elf)")
print()
