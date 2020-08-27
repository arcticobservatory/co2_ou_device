import unittest

try:
    import pycom
    import machine
except:
    import mock_apis
    pycom = mock_apis.MockPycom()
    machine = mock_apis.MockMachine()

import logging
_logger = logging.getLogger("mock_apis")
_logger.setLevel(logging.CRITICAL)

class TestWdtBehavior(unittest.TestCase):

    def test_wdt_init_call(self):
        # Pycom firmware raises if you attempt to give the timeout as positional
        with self.assertRaises(TypeError):
            wdt = machine.WDT(1000*60*60)

        with self.assertRaises(TypeError):
            wdt = machine.WDT(timeout=None)

        # Correct usage
        wdt = machine.WDT(timeout=1000*60*60)
        wdt.init(1000*60*60)

class TestPycomNvRam(unittest.TestCase):

    def test_pycom_nv_behavior(self):
        pycom.nvs_set("test_key_asdf", 1234)
        val = pycom.nvs_get("test_key_asdf")
        self.assertEqual(val, 1234)

        pycom.nvs_set("test_key_asdf", 5678)
        val = pycom.nvs_get("test_key_asdf")
        self.assertEqual(val, 5678)

        pycom.nvs_erase("test_key_asdf")

        # get non-existent key
        with self.assertRaises(ValueError):
            pycom.nvs_get("test_key_asdf")

        # double-erase
        with self.assertRaises(KeyError):
            pycom.nvs_erase("test_key_asdf")
