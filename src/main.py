# Turn off heartbeat
import pycom
pycom.heartbeat(False)

# Configure logging
import logging
logging.basicConfig(level=logging.INFO)

# Do self-test
import co2unit_hw
import co2unit_self_test

#co2unit_hw.pinset_on_boot(co2unit_hw.PINSET_BREADBOARD)
#co2unit_hw.pinset_on_boot(co2unit_hw.PINSET_PRODUCTION)

hw = co2unit_hw.Co2UnitHw()
hw.power_peripherals(True)

co2unit_self_test.quick_check(hw)
#co2unit_self_test.test_lte_ntp(hw)
co2unit_self_test.show_boot_flags()
print("Failure flags: {:#018b}".format(co2unit_self_test.failures))

co2unit_self_test._logger.setLevel(logging.DEBUG)
co2unit_self_test.display_errors_led()

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
