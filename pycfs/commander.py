
from __future__ import print_function

from builtins import bytes

import socket
import struct

class UDPCommander(object):

    def __init__(self, host, port):
        """
        """

        self.host = host
        self.port = port

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(self, cmd_bytes):
        """
        send a UDP command message
        """

        sent_size = self.socket.sendto(cmd_bytes, (self.host, self.port))
        if sent_size < len(cmd_bytes):
            print('ERROR: Incomplete send: {} of {} bytes sent.'.format(sent_size, len(cmd_bytes)))
