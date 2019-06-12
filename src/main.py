# Turn off heartbeat
import pycom
pycom.heartbeat(False)

# Configure logging
import logging
logging.basicConfig(level=logging.INFO)

# Do self-test
import co2unit_hw
import co2unit_self_test

#co2unit_hw.pinset_on_boot(co2unit_hw.PINSET_BREADBOARD) # Set to use breadboard pinset

hw = co2unit_hw.Co2UnitHw()
hw.power_peripherals(True)

co2unit_self_test.quick_check(hw)
co2unit_self_test.test_lte_ntp(hw.ertc())
print("Failure flags: {:b}".format(co2unit_self_test.failures))
co2unit_self_test.show_boot_flags()
