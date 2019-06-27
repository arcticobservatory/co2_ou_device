from machine import Timer
import time
import network

import logging
_logger = logging.getLogger("co2unit_comm")

import usocket
import urequests

SERVER = "http://129.242.17.212/"

def hello_server_world():
    _logger.info("Server hello world...")

    chrono = Timer.Chrono()
    chrono.start()

    try:
        _logger.info("Giving LTE time to boot before initializing it...")
        time.sleep_ms(1000)

        _logger.info("Init LTE...")
        chrono.reset()
        lte = network.LTE()
        _logger.info("LTE init ok (%d ms)", chrono.read_ms())

        #_logger.info("Doing an LTE reset for paranioa")
        #chrono.reset()
        #lte.reset()
        #_logger.info("LTE reset ok (%d ms)", chrono.read_ms())

        _logger.info("LTE attaching... (up to 2 minutes)")
        chrono.reset()
        lte.attach()
        while True:
            if lte.isattached(): break
            if chrono.read_ms() > 150 * 1000: raise TimeoutError()
        _logger.info("LTE attach ok (%d ms). Connecting...", chrono.read_ms())

        chrono.reset()
        lte.connect()
        while True:
            if lte.isconnected():
                break
            elif chrono.read_ms() > 120 * 1000:
                raise TimeoutError("LTE did not attach after %d ms" % chrono.read_ms())
        _logger.info("LTE connect ok (%d ms)", chrono.read_ms())

        _logger.info("Contacting server %s", SERVER)
        resp = urequests.get(SERVER)
        _logger.info("Response (%s): %s", resp.status_code, resp.text)

    finally:
        if lte:
            try:
                if lte.isconnected():
                    chrono.reset()
                    lte.disconnect()
                    _logger.info("LTE disconnected (%d ms)", chrono.read_ms())
                if lte.isattached():
                    chrono.reset()
                    lte.dettach()
                    _logger.info("LTE detached (%d ms)", chrono.read_ms())
            finally:
                chrono.reset()
                lte.deinit()
                _logger.info("LTE deinit-ed (%d ms)", chrono.read_ms())

    return lte
