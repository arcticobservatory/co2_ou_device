import logging
import json
import os
import time

_logger = logging.getLogger("co2unit_updates")

# Recommended by pycom docs
# https://docs.pycom.io/firmwareapi/pycom/pycom.html#pycomotastart
OTA_BLOCKSIZE = const(4096)

# Index of size field in os.stat() result
ST_SIZE = const(6)

def do_pycom_ota(appimg):
    # NOT RECOMMENDED TO DO WHEN DEPLOYED
    #
    # After testing this with version 1.18.2.r7, on first reboot there was an error
    #
    # E (116) esp_image: invalid segment length 0xf3e502ad
    #
    # It went away on subsequent reboots. But after that, on some reboots,
    # there would be a syntax error loading one file or another, even though
    # the file had not changed. After another reboot, they would go away.

    import pycom

    imgsize = os.stat(appimg)[ST_SIZE]

    with open(appimg, "rb") as f:
        buf = bytearray(OTA_BLOCKSIZE)
        view = memoryview(buf)
        size = 0
        _logger.info("Starting OTA update...")
        pycom.ota_start()
        while True:
            chunk = f.readinto(buf)
            if chunk == 0:
                break
            pycom.ota_write(view[:chunk])
            size += chunk
            _logger.debug("Progress: %d / %d bytes", size, imgsize)
        pycom.ota_finish()
        _logger.info("Finished OTA update")

def do_modem_upgrade(dup, elf):
    # NOT RECOMMENDED TO DO WHEN DEPLOYED
    #
    # - The upgrade does not report success or failure programmatically, only
    #   in print output.
    # - You might need to do a full power cycle, which requires physical access
    #   (or a redundant microcontroller).

    # https://docs.pycom.io/tutorials/lte/firmware.html
    import sqnsupgrade
    sqnsupgrade.run(dup, elf)

    # Notes from initial testing:
    #
    # First try:
    # - AT auto-negotiation failed after a long timeout (LTE was off at boot).
    # - It did throw an error, just printed a failure message.
    # - The docs say you need to do a full power cycle to continue after an
    #   error. So doing this in the field might be dangerous.
