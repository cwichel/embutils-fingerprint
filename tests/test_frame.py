#!/usr/bin/python
# -*- coding: ascii -*-
"""
Test: Fingerprint sensor implementation capabilities:

* Serialization
* Deserialization
* Object comparison

:date:      2021
:author:    Christian Wiche
:contact:   cwichel@gmail.com
:license:   The MIT License (MIT)
"""

# External ======================================
import unittest


# Internal ======================================
from fpsensor.api import FpPID
from fpsensor.packet import FpPacket


# Definitions ===================================
class Test(unittest.TestCase):
    """
    Test basic packet operations.
    """
    def test_serialize(self):
        """
        Check if the serialization of a packet is being done correctly.
        """
        # Create packet for image capture
        data = bytearray([0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x01, 0x00, 0x03, 0x01, 0x00, 0x05])
        pack = FpPacket(pid=FpPID.COMMAND, packet=bytearray([0x01]))

        # Compare
        assert pack.serialize() == data

    def test_deserialize(self):
        """
        Check if the deserialization of a packet is being done correctly.
        """
        # Deserialize image capture
        data  = bytearray([0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x01, 0x00, 0x03, 0x01, 0x00, 0x05])
        pack = FpPacket.deserialize(data=data)

        # Check
        assert pack is not None
        assert pack.serialize() == data

    def test_comparison(self):
        """
        Check if the comparison of packets is being done correctly.
        """
        # Create packets
        pack_1 = FpPacket(pid=FpPID.COMMAND, packet=bytearray([0x07]))
        pack_2 = FpPacket(pid=FpPID.COMMAND, packet=bytearray([0x07]))
        pack_3 = FpPacket(pid=FpPID.ACK, packet=bytearray([0x08]))

        # Compare
        assert pack_1 is not pack_2
        assert pack_1 == pack_2
        assert pack_1.serialize() == pack_2.serialize()

        assert pack_1 != pack_3
        assert pack_1.serialize() != pack_3.serialize()


# Execution =====================================
if __name__ == '__main__':
    # Execute the tests
    unittest.main()
