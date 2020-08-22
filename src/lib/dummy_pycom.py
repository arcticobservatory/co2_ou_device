"""Dummy implementation of Pycom's API, for testing"""

import logging
_logger = logging.getLogger("dummy_pycom")
_logger.setLevel(logging.DEBUG)

_nvram = {}

def nvs_get(key):
    try:
        return _nvram[key]
    except KeyError as e:
        raise ValueError(e)

def nvs_set(key, val):
    _logger.debug("nvs_set(%s, %s)", key, val)
    _nvram[key] = val

def nvs_erase(key):
    del(_nvram[key])
