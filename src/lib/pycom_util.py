"""
Gloss over some tricky spots in Pycom's API
"""

import pycom

def nvs_get(key, value, default=None):
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

def mk_on_boot_fn(key):
    def on_boot_fn(value=None, default=None, erase=False):
        if erase:
            return nvs_erase(key)
        elif value == None:
            return nvs_get(key, default)
        else:
            return pycom.nvs_set(key, value)

    return on_boot_fn
