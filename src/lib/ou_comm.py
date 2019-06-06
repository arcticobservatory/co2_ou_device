# Copied from Telenor's StartIot tutorial
# https://github.com/TelenorStartIoT/FiPyDevKitCatM1

from network import LTE
import usocket as socket
import re
import machine
import utime
import pycom

class StartIot():

    def __init__(self):
        self.lte = LTE()
        self.initModem()


    # METHOD FOR PRETTY PRINTING AT COMMANDS
    def send_at_cmd_pretty(self, cmd):
        response = self.lte.send_at_cmd(cmd)
        if response != None:
            lines=response.split('\r\n')
            print("Response is:< ")
            for line in lines:
                if len(line.strip()) != 0:
                    print(line)
            print(">")
        else:
            print("Response is None...")
        return response

    # SETUP AND START THE MODEM - ATTACH TO THE NETWORK
    def initModem(self):
        print ("Starting modem...")
        self.send_at_cmd_pretty('AT+CFUN=0')
        # Change this if you are using the NB1 network (uncomment the next 4 lines)
        #self.send_at_cmd_pretty('AT+CEMODE=0')
        #self.send_at_cmd_pretty('AT+CEMODE?')
        #self.send_at_cmd_pretty('AT!="clearscanconfig"')
        #self.send_at_cmd_pretty('AT!="addscanfreq band=20 dl-earfcn=6352"')
        # End change this ....
        self.send_at_cmd_pretty('AT+CGDCONT=1,"IP","mda.ee"')
        self.send_at_cmd_pretty('AT+CFUN=1')
        self.send_at_cmd_pretty('AT+CSQ')

        print ("Waiting for attachement (To Radio Access Network)...")
        timer_start = utime.ticks_ms()
        while not self.lte.isattached():
            if (utime.ticks_ms() - timer_start) > 120000:
                machine.reset()
            machine.idle()
        else:
            print ("Attached (To Radio Access Network)...")

    # CONNECT TO THE NETWORK
    def connect(self):
        if not self.lte.isattached():
            raise Exception('NOT ATTACHED... call initModem() first')
        print ("Waiting for connection (To IP network)...")
        self.lte.connect()
        # Wait until we get connected to network
        while not self.lte.isconnected():
            machine.idle()
        print ("Connected (To IP network)!")

    # OPEN SOCKET AND SEND DATA
    def send(self, data):
        if not self.lte.isconnected():
            raise Exception('NOT CONNECTED')
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        IP_address = socket.getaddrinfo('172.16.15.14', 1234)[0][-1]
        s.connect(IP_address)
        s.send(data)
        s.close()

    def disconnect(self):
        if self.lte.isconnected():
            self.lte.disconnect()

    def dettach(self):
        if self.lte.isattached():
            self.lte.dettach()
        self.lte.send_at_cmd('AT+CFUN=0')
        print("Modem offline")
