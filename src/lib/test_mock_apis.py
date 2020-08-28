import unittest
import mock_apis

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

    def test_pycom_nv_set_get(self):
        pycom.nvs_set("test_key_asdf", 1234)
        val = pycom.nvs_get("test_key_asdf")
        self.assertEqual(val, 1234)

        pycom.nvs_set("test_key_asdf", 5678)
        val = pycom.nvs_get("test_key_asdf")
        self.assertEqual(val, 5678)

    @unittest.skipIf(not mock_apis.PYCOM_EXCEPTION_ON_NONEXISTENT_KEY,
            "Test is for firmware variants that throw exceptions")
    def test_pycom_nv_get_nonexistent_raise_error(self):
        pycom.nvs_erase("test_key_asdf")

        # get non-existent key
        with self.assertRaises(mock_apis.PYCOM_EXCEPTION_ON_NONEXISTENT_KEY):
            pycom.nvs_get("test_key_asdf")

    @unittest.skipIf(mock_apis.PYCOM_EXCEPTION_ON_NONEXISTENT_KEY,
            "Test is for firmware variants that return None")
    def test_pycom_nv_get_nonexistent_return_none(self):
        pycom.nvs_erase("test_key_asdf")

        # get non-existent key
        val = pycom.nvs_get("test_key_asdf")
        self.assertEqual(val, None)

    def test_pycom_nv_double_erase(self):
        pycom.nvs_set("test_key_asdf", 1234)
        pycom.nvs_erase("test_key_asdf")
        with self.assertRaises(KeyError):
            pycom.nvs_erase("test_key_asdf")
