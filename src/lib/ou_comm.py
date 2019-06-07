# Adapted from code Sergiusz gave me

# Note: this only seems to work if lte.lte_en_on_boot() is True when you power on

import socket
import ssl
import time
from network import LTE

def test_connect():
    lte = LTE()

    def send_at_cmd_pretty(cmd):
        response = lte.send_at_cmd(cmd).split('\r\n')
        for line in response:
            line = line.replace('\r', '').replace('\n', '')
            if len(line) == 0:
                continue
            print("> {}".format(line))

    send_at_cmd_pretty('AT+CFUN=0')
    send_at_cmd_pretty('AT!="clearscanconfig"')
    send_at_cmd_pretty('AT!="addscanfreq band=20 dl-earfcn=6400"')
    send_at_cmd_pretty('AT+CGDCONT=1,"IP","telenor.iot"')
    send_at_cmd_pretty('AT+CEREG=2')
    send_at_cmd_pretty('AT+CFUN=1')

    print('Trying to attach!')
    while not lte.isattached():
        time.sleep(1)
    print('Attached!')

    lte.connect()
    while not lte.isconnected():
        time.sleep(0.25)
    print('Connected!')
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # s = ssl.wrap_socket(s)
    # s.connect(socket.getaddrinfo('ident.me', 443)[0][-1])
    # addr = socket.getaddrinfo('nogne.qlown.me', 31415)[0][-1]
    addr = ('193.90.243.78', 31415)
    s.sendto(b"{\"test\":\"test message\"}", addr)
    # print(s.recv(4096))
    s.close()

    lte.disconnect()
    lte.dettach()
