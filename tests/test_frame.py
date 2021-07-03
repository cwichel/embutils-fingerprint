#!/usr/bin/python
# -*- coding: ascii -*-
"""
Fingerprint frame test suite.

@date:      2021
@author:    Christian Wiche
@contact:   cwichel@gmail.com
@license:   The MIT License (MIT)
"""

import unittest

from fpsensor.api import FpPID
from fpsensor.frame import FpFrame


# Test Definitions ==============================
class TestFrame(unittest.TestCase):
    """Basic reference tests using the GeaFrame example.
    """
    def test_serialize(self):
        """Check if the serialization of a frame is being done correctly.
        """
        # Create frame for image capture
        data = bytearray([0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x01, 0x00, 0x03, 0x01, 0x00, 0x05])
        frame = FpFrame(pid=FpPID.COMMAND, packet=bytearray([0x01]))

        # Compare
        assert frame.serialize() == data

    def test_deserialize(self):
        """Check if the deserialization of a frame is being done correctly.
        """
        # Deserialize image capture
        data  = bytearray([0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x01, 0x00, 0x03, 0x01, 0x00, 0x05])
        frame = FpFrame.deserialize(data=data)

        # Check
        assert frame is not None
        assert frame.serialize() == data

    def test_comparison(self):
        """Check if the comparison of frames is being done correctly.
        """
        # Create frames
        frame_1 = FpFrame(pid=FpPID.COMMAND, packet=bytearray([0x07]))
        frame_2 = FpFrame(pid=FpPID.COMMAND, packet=bytearray([0x07]))
        frame_3 = FpFrame(pid=FpPID.ACK, packet=bytearray([0x08]))

        # Compare
        assert frame_1 is not frame_2
        assert frame_1 == frame_2
        assert frame_1.serialize() == frame_2.serialize()

        assert frame_1 != frame_3
        assert frame_1.serialize() != frame_3.serialize()


# Test Execution ================================
if __name__ == '__main__':
    unittest.main()
