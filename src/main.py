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
