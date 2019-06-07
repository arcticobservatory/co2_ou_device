# Adapted from code Sergiusz gave me

# Note: this only seems to work if pycom.lte_modem_en_on_boot() is True when you power on

import socket
import ssl
import time

from network import LTE
import pycom

import logging

import polling

_logger = logging.getLogger("ou_comm")

def test_connect():
    _logger.debug("pycom.lte_modem_en_on_boot() == %s",
            pycom.lte_modem_en_on_boot())

    _logger.debug("LTE constructor")
    lte = LTE()

    _logger.debug("lte.init()")
    lte.init()

    _logger.debug("lte.attach()")
    lte.attach()

    _logger.info("Waiting for LTE attach")
    _, attach_ms = polling.poll_wait_ms(lte.isattached, timeout_ms=30*1000, sleep_ms=1)
    _logger.info("LTE attached in %s ms", attach_ms)

    _logger.debug("lte.connect()")
    lte.connect()

    _logger.info("Waiting for LTE connect")
    _, connect_ms = polling.poll_wait_ms(lte.isconnected, timeout_ms=30*1000, sleep_ms=1)
    _logger.info('LTE connected in %d ms', connect_ms)

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

    _logger.debug("lte.disconnect()")
    lte.disconnect()
    _logger.debug("lte.dettach()")
    lte.dettach()
