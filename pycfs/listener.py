
from __future__ import print_function

from builtins import bytes

import sys
import threading
import socket
import struct
import select

from .serialization import TelemetryFactory

class UDPListener(object):
    def __init__(self, host, port, type_specs, max_size=8192, endianness='litte'):
        self.cb_dict = {}

        self.host = host
        self.port = port

        self.MAX_MSG_SIZE = max_size

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(1.0)
        self.socket.bind((host,port))

        self.tfac = TelemetryFactory(type_specs, endianness)

        self.running = True
        self.thread = threading.Thread(target=self.listener_thread)

    def start(self):
        self.thread.start()

    def shutdown(self):
        print('Shutting down UDPListener...')
        self.running = False
        self.thread.join()
        self.socket.close()

    def listener_thread(self):

        print('Starting listener thread...')

        while self.running:
            readable, writable, exceptional = select.select([self.socket],[],[self.socket], 1.0)
            if not readable:
                continue

            #print('Receiving...')
            data, sender_addr = self.socket.recvfrom(self.MAX_MSG_SIZE)

            if len(data) == self.MAX_MSG_SIZE:
                raise Exception("Socket received {} bytes, full message not received.".format(self.MAX_MSG_SIZE))

            try:
                apid, seq, data_len, stamp  = self.tfac.unpack_header(data)
            except ValueError as err:
                print('ERROR: Could not unpack packet header: {}'.format(err))
                continue

            #print('Got message with apid: 0x{:04x} data_len: {} actual size: {}'.format(apid, data_len, len(data)))

            mid = apid

            for spec,cbs in self.cb_dict.get(mid,[]):
                cstruct = self.tfac.unpack_payload(data,spec)
                try:
                    for cb in cbs:
                        cb(cstruct)
                except Exception as ex:
                    print('ERROR: Exception in callback for MID {}: {}'.format(mid, ex))

        print('Listener thread terminated.')


    def listen(self, mid, spec, cbs):
        """
        call callback(s) when receiving message with message id mid
        cbs is a list of callbacks, each with signature:
            cb(stamp, packet)
        """

        print('Listening to MID 0x%x' % mid)

        if mid not in self.cb_dict:
            self.cb_dict[mid] = []

        # support old use case of passing a single function as callback
        if hasattr(cbs, '__call__'):
            cbs = [cbs]

        self.cb_dict[mid].append((spec,cbs))


