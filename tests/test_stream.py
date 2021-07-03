#!/usr/bin/python
# -*- coding: ascii -*-
"""
Fingerprint frame stream test suite.

@date:      2021
@author:    Christian Wiche
@contact:   cwichel@gmail.com
@license:   The MIT License (MIT)
"""

import time
import unittest
from embutils.serial.core import SerialDevice, FrameStream
from embutils.utils import UsbID, LOG_SDK

from fpsensor.api import FpPID
from fpsensor.frame import FpFrame, FpFrameHandler

LOG_SDK.enable()


# Test Definitions ==============================
class TestFrameStream(unittest.TestCase):
    """Basic streaming tests using the SimpleFrame example.
    """
    def test_send_and_receive(self):
        """Send and receive a frame using the frame stream on a looped serial device.
        Test if the transmitted/received frames are the same.
        """
        frame = FpFrame(pid=FpPID.COMMAND, packet=bytearray([0x01]))
        self.send_and_receive(send=frame, handler=FpFrameHandler())

    @staticmethod
    def send_and_receive(send: FpFrame, handler: FpFrameHandler) -> None:
        """Simulate a serial device on loop mode and perform a comparison between
        the data being received and sent.
        """
        # Stop flag
        is_ready = False

        # Manage frame reception
        def on_frame_received(recv: FpFrame):
            nonlocal send, is_ready

            assert recv is not None
            assert recv == send

            is_ready = True

        # Initialize frame stream
        fh = handler
        sd = SerialDevice(uid=UsbID(vid=0x1234, pid=0x5678), looped=True)
        fs = FrameStream(serial_device=sd, frame_handler=fh)
        fs.on_frame_received += lambda frame: on_frame_received(recv=frame)

        # Send frame
        fs.send_frame(frame=send)

        # Maintain alive the process
        while not is_ready:
            time.sleep(0.01)


# Test Execution ================================
if __name__ == '__main__':
    unittest.main()
