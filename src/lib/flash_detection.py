import machine
import pycom
from machine import Pin


# integrate this in your code and remove the function:
def test_flash_detection():
    if machine.wake_reason()[0] == machine.PIN_WAKE:
        flash_detect_main()
# end


def go_back_to_sleep():
    machine.pin_deepsleep_wakeup(pins=['P2'], mode=machine.WAKEUP_ANY_HIGH)
    machine.deepsleep(machine.remaining_sleep_time())
    

def flash_detect_main():
    flash_counter = pycom.nvs_get('flash_counter')
    if flash_counter is None:
        flash_counter = 0
    flash_counter += 1
    pycom.nvs_set('flash_counter', flash_counter)
    go_back_to_sleep()