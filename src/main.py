# Turn off heartbeat
import pycom
pycom.heartbeat(False)

# Configure logging
import logging
logging.basicConfig(level=logging.INFO)

# Do self-test
import co2unit_hw
import co2unit_self_test

hw = co2unit_hw.Co2UnitHw()
#hw.select_breadboard_pins()        # Select pins for breadboard prototype
hw.mosfet_pin()(True)
co2unit_self_test.quick_check(hw)
co2unit_self_test.test_lte_ntp(hw.ertc())
print("Failure flags: {:b}".format(co2unit_self_test.failures))
co2unit_self_test.show_boot_flags()
