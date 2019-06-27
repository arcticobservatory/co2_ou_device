import time
import network

import logging
_logger = logging.getLogger("co2unit_comm")

import usocket
import urequests

SERVER = "http://129.242.17.212/"

def hello_server_world():
    _logger.info("Server hello world...")

    try:
        _logger.info("Init LTE...")
        start_ticks = time.ticks_ms()
        lte = network.LTE()
        elapsed = time.ticks_diff(start_ticks, time.ticks_ms())
        _logger.info("LTE init ok (%d ms). Attaching... (up to 2 minutes)", elapsed)

        start_ticks = time.ticks_ms()
        lte.attach()
        while True:
            elapsed = time.ticks_diff(start_ticks, time.ticks_ms())
            if lte.isattached(): break
            if elapsed > 150 * 1000: raise TimeoutError()
        _logger.info("LTE attach ok (%d ms). Connecting...", elapsed)

        start_ticks = time.ticks_ms()
        lte.connect()
        while True:
            elapsed = time.ticks_diff(start_ticks, time.ticks_ms())
            if lte.isconnected():
                break
            elif elapsed > 120 * 1000:
                raise TimeoutError("LTE did not attach after %d ms" % elapsed)
        _logger.info("LTE connect ok (%d ms)", elapsed)

        _logger.info("Contacting server %s", SERVER)
        resp = urequests.get(SERVER)
        _logger.info("Response (%s): %s", resp.status_code, resp.text)

    finally:
        if lte:
            try:
                start_ticks = time.ticks_ms()
                if lte.isconnected():
                    lte.disconnect()
                    _logger.info("LTE disconnected")
                if lte.isattached():
                    lte.dettach()
                    _logger.info("LTE detached")
            finally:
                lte.deinit()
                elapsed = time.ticks_diff(start_ticks, time.ticks_ms())
                _logger.info("LTE deinit-ed (%d ms)", elapsed)

                start_ticks = time.ticks_ms()
                _logger.info("Resetting...")
                lte.reset()
                _logger.info("LTE reset (%d ms)", elapsed)
                elapsed = time.ticks_diff(start_ticks, time.ticks_ms())
