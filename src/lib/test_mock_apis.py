import unittest

try:
    import pycom
except:
    import mock_apis
    pycom = mock_apis.MockPycom()

import logging
_logger = logging.getLogger("dummy_pycom")
_logger.setLevel(logging.CRITICAL)

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
