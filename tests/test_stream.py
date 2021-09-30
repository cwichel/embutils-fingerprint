#!/usr/bin/python
# -*- coding: ascii -*-
"""
Test: Fingerprint sensor stream capabilities:

* Send, receive and process a packet.

@date:      2021
@author:    Christian Wiche
@contact:   cwichel@gmail.com
@license:   The MIT License (MIT)
"""

# External ======================================
import time
import unittest
from embutils.serial import Device, Stream
from embutils.utils import SDK_LOG

# Internal ======================================
from fpsensor.api import FpPID
from fpsensor.packet import FpPacket, FpStreamFramingCodec


# Definitions ===================================
SDK_LOG.enable()


# Definitions ===================================
class Test(unittest.TestCase):
    """
    Test basic packet streaming.
    """
    def test_send_and_receive(self):
        """
        Send and receive a packet using the stream and check if data is the same.
        """
        pack = FpPacket(pid=FpPID.COMMAND, packet=bytearray([0x01]))
        self.send_and_receive(send=pack, codec=FpStreamFramingCodec())

    @staticmethod
    def send_and_receive(send: FpPacket, codec: FpStreamFramingCodec) -> None:
        """
        Simulates a serial device on loop mode and performs a comparison between the data being sent/received.
        """
        # Stop flag
        is_ready = False

        # Manage reception
        def on_received(recv: FpPacket):
            nonlocal send, is_ready
            assert recv is not None
            assert recv == send
            is_ready = True

        # Manage connection
        def on_connected():
            fs.send(item=send)

        # Initialize stream
        sd = Device(looped=True)
        fs = Stream(device=sd, codec=codec)

        # Add events
        fs.on_connect += on_connected
        fs.on_receive += lambda item: on_received(recv=item)

        # Maintain alive the process
        while not is_ready:
            time.sleep(0.01)


# Execution =====================================
if __name__ == '__main__':
    # Execute the tests
    unittest.main()
