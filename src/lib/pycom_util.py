"""
Gloss over some tricky spots in Pycom's API and firmware
"""

import pycom
import machine

def nvs_get(key, default=None):
    """ Reads non-volatile state and returns default if not defined

    Some Pycom versions return None if the value is undefined. Some throw an
    error. This function suppresses the error and adds a default feature.
    """

    try:
        return pycom.nvs_get(key) or default
    except:
        return default

def nvs_erase(key):
    """ Erases a key from non-volatile memory. Does not complain if key does not exist.

    Some pycom versions throw an error if the key you want to erase is not
    there. This function does not, making the action idempotent.
    """

    try:
        return pycom.nvs_erase(key)
    except:
        return None

def mk_on_boot_fn(key, default=None):
    def on_boot_fn(value=None, default=default, erase=False):
        if erase:
            return nvs_erase(key)
        elif value == None:
            return nvs_get(key, default=default)
        else:
            return pycom.nvs_set(key, value)

    return on_boot_fn

class SpiWrapper(machine.SPI):
    """
    Wrap the SPI driver for compatibility with the SDCard driver

    The SDCard driver calls SPI read commands with two positional arguments:

        self.spi.read(1, 0xff)

    The Pycom firmware's SPI class does not support that. It expects the call
    to use keyword arguments:

        self.spi.read(1, write=0xff)

    This class translates the SDCard calls to the keyword call that the Pycom
    SPI class understands.
    """

    def read(self, nbytes, token):
        return super().read(nbytes, write=token)

    def readinto(self, buf, token):
        return super().readinto(buf, write=token)

class PinWrapper(machine.Pin):
    """
    Wrap the Pin class for compatibility with the SDCard driver

    The SDCard driver sets pins with methods .high() and .low().

    The Pycom firmware's Pin class does not support this. The object itself is
    callable and accepts a value. This class translates the SDCard calling
    style to one the Pycom Pin class understands.
    """

    def high(self):
        return self(1)

    def low(self):
        return self(0)
