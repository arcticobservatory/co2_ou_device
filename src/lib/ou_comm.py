# Adapted from code Sergiusz gave me

# Note: this only seems to work if pycom.lte_modem_en_on_boot() is True when you power on

import socket
import ssl
import time

from network import LTE
import pycom

import logging

import flaky
import stopwatch

_logger = logging.getLogger("ou_comm")

class OuCommError(Exception): pass
class InitModemError(OuCommError): pass

class OuComm(object):

    def __init__(self):
        self.lte = None

    def lte_connect(self):
        _logger.debug("pycom.lte_modem_en_on_boot() == %s",
                pycom.lte_modem_en_on_boot())

        timer = stopwatch.StopWatch(logger=_logger)

        timer.start_ms("LTE constructor")
        try:
            self.lte = flaky.retry_call( LTE, wait_ms=10)
            lte = self.lte
        except OSError as e:
            raise InitModemError(e)
        timer.stop()

        timer.start_ms("lte.attach()")
        lte.attach()
        timer.stop()

        timer.start_ms("LTE isattached")
        _, attach_ms = timer.wait_for(lte.isattached,
                timeout=60*1000, sleep=10)
        _logger.info('LTE attached in %d ms', attach_ms)

        timer.start_ms("lte.connect()")
        lte.connect()
        timer.stop()

        timer.start_ms("LTE isconnected")
        _, connect_ms = timer.wait_for(lte.isconnected,
                timeout=5*1000, sleep=1)
        _logger.info('LTE connected in %d ms', connect_ms)

    def lte_disconnect(self):
        timer = self.timer

        timer.start_ms("lte.disconnect()")
        self.lte.disconnect()
        timer.stop()

        timer.start_ms("lte.detach()")
        self.lte.dettach()
        timer.stop()

        timer.start_ms("lte.deinit()")
        self.lte.deinit()
        timer.stop()

    def send_test_msg(self):

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
