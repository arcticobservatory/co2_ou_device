# Adapted from code Sergiusz gave me

# Note: this only seems to work if pycom.lte_modem_en_on_boot() is True when you power on

import socket
import ssl
import time

from network import LTE
import machine
import pycom

import logging

import stopwatch

_logger = logging.getLogger("ou_comm")

class OuCommError(Exception): pass
class InitModemError(OuCommError): pass

class OuComm(object):

    def __init__(self):
        self.lte = None

    def set_persistent_settings(self):
        if pycom.lte_modem_en_on_boot():
            _logger.info("LTE on boot was enabled. Disabling.")
            pycom.lte_modem_en_on_boot(False)

        if pycom.wifi_on_boot():
            _logger.info("Wifi on boot was enabled. Disabling.")
            pycom.wifi_on_boot(False)

    def lte_connect(self):
        _logger.info("Attempting to connect LTE")
        timer = stopwatch.StopWatch(logger=_logger)

        timer.start_ms("LTE constructor")
        try:
            lte = LTE()
            self.lte = lte
            _logger.info("LTE constructor OK")
            _logger.info("Boot status: lte on boot %s; reset_cause %s",
                    pycom.lte_modem_en_on_boot(), machine.reset_cause())
        except OSError as e:
            _logger.error("LTE constructor FAILED. %s: %s", type(e).__name__, e)
            _logger.info("Boot status: lte on boot %s; reset_cause %s",
                    pycom.lte_modem_en_on_boot(), machine.reset_cause())
            raise InitModemError(e)
        timer.stop()

        timer.start_ms("lte.attach()")
        lte.attach()
        timer.stop()

        timer.start_ms("LTE isattached")
        # CAT-M1 spec says up to 2 minutes for attach
        _, attach_ms = timer.wait_for(lte.isattached,
                timeout=120*1000, sleep=10)
        _logger.info('LTE attached in %d ms', attach_ms)

        timer.start_ms("lte.connect()")
        lte.connect()
        timer.stop()

        timer.start_ms("LTE isconnected")
        _, connect_ms = timer.wait_for(lte.isconnected,
                timeout=5*1000, sleep=1)
        _logger.info('LTE connected in %d ms', connect_ms)

    def lte_disconnect(self):
        timer = stopwatch.StopWatch(logger=_logger)

        timer.start_ms("lte.disconnect()")
        self.lte.disconnect()
        timer.stop()
        _logger.info('LTE disconnected')

        timer.start_ms("lte.detach()")
        self.lte.dettach()
        timer.stop()
        _logger.info('LTE detached')

        timer.start_ms("lte.deinit()")
        self.lte.deinit()
        timer.stop()
        _logger.info('LTE de-initialized')

    def send_test_msg(self):
        timer = stopwatch.StopWatch(logger=_logger)

        _logger.debug("Opening socket")
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # s = ssl.wrap_socket(s)
        # s.connect(socket.getaddrinfo('ident.me', 443)[0][-1])
        # addr = socket.getaddrinfo('nogne.qlown.me', 31415)[0][-1]
        addr = ('193.90.243.78', 31415)
        _logger.debug("Sending test packet")
        s.sendto(b"{\"test\":\"test message\"}", addr)
        # print(s.recv(4096))
        _logger.debug("Closing socket")
        s.close()