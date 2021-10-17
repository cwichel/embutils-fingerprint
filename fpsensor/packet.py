#!/usr/bin/python
# -*- coding: ascii -*-
"""
Fingerprint packet.

:date:      2021
:author:    Christian Wiche
:contact:   cwichel@gmail.com
:license:   The MIT License (MIT)
"""

import dataclasses as dc
import typing as tp

from embutils.serial import Device, AbstractSerializedStreamCodec
from embutils.utils import IntEnum, AbstractSerialized

from .api import ADDRESS, FpPID, to_bytes, from_bytes


# -->> Definitions <<------------------


# -->> API <<--------------------------
@dc.dataclass
class FpPacket(AbstractSerialized):
    """
    Fingerprint packet structure definition.

    Structure:

    .. code-block::

        0: Header   : 2 byte MSB    : 0   - 1
        1: Address  : 4 byte MSB    : 2   - 5
        2: PID      : 1 byte        : 6
        3: Length   : 2 byte MSB    : 7   - 8
        4: Data     : N byte        : 9   - N
        5: Checksum : 2 byte MSB    : N+1 - N+2

    .. note::
        * Min size: `11`
        * Max size: `256`

    """
    #: Fixed packet header
    HEADER  = 0xEF01
    #: Minimum packet size
    SIZE_MIN = 11
    #: Maximum packet size
    SIZE_MAX = 256

    #: Device address
    address:    int = ADDRESS
    #: Frame type (PID)
    pid:        FpPID = FpPID.COMMAND
    #: Packet data
    packet:     bytearray = bytearray()

    @property
    def checksum(self) -> int:
        """
        Packet checksum.
        This value computes a checksum over the PID, length and packet data.
        """
        return 0xFFFF & sum(self._core())

    @property
    def length(self) -> int:
        """
        Packet length.
        By definition: `len(packet) + len(checksum)`
        """
        return len(self.packet) + 2

    def _core(self) -> bytearray:
        """
        Raw packet data. This group was defined to ease the checksum
        computation. The contents are: PID, length and packet data.
        """
        return bytearray(
            bytes([self.pid]) +
            to_bytes(value=self.length, size=2) +
            self.packet
            )

    def serialize(self) -> bytearray:
        """
        Converts the packet into a byte array.
        """
        return bytearray(
            to_bytes(value=self.HEADER, size=2) +
            to_bytes(value=self.address, size=4) +
            self._core() +
            to_bytes(value=self.checksum, size=2)
            )

    @classmethod
    def deserialize(cls, data: bytearray) -> tp.Optional['FpPacket']:
        """
        Deserialize the packet from the input bytes.
        """
        # Check minimum length
        if len(data) < cls.SIZE_MIN:
            return None

        # Check for packet fixed header
        head = from_bytes(data=data[0:2])
        if head != FpPacket.HEADER:
            return None

        # Check message PID
        if not FpPID.has_value(value=data[6]):
            return None

        # Parse packet bytes
        tmp = FpPacket(
            address=from_bytes(data=data[2:6]),
            pid=FpPID(data[6]),
            packet=data[9:-2]
            )

        # Check consistency using CRC
        pkt_len = from_bytes(data=data[7:9])
        checksum = from_bytes(data=data[-2:])
        if (pkt_len != tmp.length) or (checksum != tmp.checksum):
            return None
        return tmp


class FpStreamFramingCodec(AbstractSerializedStreamCodec):
    """
    Fingerprint framing implementation to use on streams.
    """
    class State(IntEnum):
        """
        Codec reading states.
        """
        WAIT_HEAD   = 0x01      # Wait for the header to be detected
        WAIT_BASE   = 0x02      # Wait for length
        WAIT_DATA   = 0x03      # Wait for remaining data

    def __init__(self):
        """
        This class don't require any input from the user to be initialized.
        """
        self._state = self.State.WAIT_HEAD
        self._recv  = bytearray()
        self._count = 0

    def encode(self, data: AbstractSerialized) -> bytearray:
        """
        Encodes (serializes) the input packet.
        """
        return data.serialize()

    def decode(self, data: bytearray) -> tp.Optional[AbstractSerialized]:
        """
        Decodes (deserializes) the input bytes into a packet.
        """
        try:
            return FpPacket.deserialize(data=data)
        except Exception as _:
            return None

    def decode_stream(self, device: Device) -> tp.Optional[AbstractSerialized]:
        """
        Defines how to read the serial device to retrieve a fingerprint packet.
        """
        # Get all the available bytes and put them into a buffer
        recv = device.read(size=device.serial.in_waiting) if device.is_open else None
        if recv is None:
            raise ConnectionError(f"Connection error while reading from {device}")

        # Process received bytes
        self._recv.extend(recv)
        while True:
            # Don't continue if we dont have at least the minimum packet length
            if len(self._recv) < FpPacket.SIZE_MIN:
                return None

            # Process data depending on state...
            if self._state == self.State.WAIT_HEAD:
                # Find the header and set it as start
                index = self._recv.find(to_bytes(value=FpPacket.HEADER, size=2))
                if index == -1:
                    # Preserve the last byte (to detect possible header)
                    self._recv = self._recv[-1:]
                    break
                # Prepare data
                self._recv  = self._recv[index:]
                self._state = self.State.WAIT_BASE

            elif self._state == self.State.WAIT_BASE:
                # Check for length to define missing bytes
                tmp = from_bytes(data=self._recv[7:9])
                self._count = FpPacket.SIZE_MIN + tmp - 2
                self._state = self.State.WAIT_DATA

            elif self._state == self.State.WAIT_DATA:
                # Wait for bytes
                if len(self._recv) < self._count:
                    break
                # Parse and emit (if possible)
                recv = FpPacket.deserialize(data=self._recv[0:self._count])
                self._recv = self._recv[self._count:] if recv else self._recv[2:]
                self._restart()
                return recv

            else:
                # Shouldn't be here...
                self._restart()
                return None

    def _restart(self) -> None:
        """
        Restarts the packet handler state machine.
        """
        self._state = self.State.WAIT_HEAD
        self._count = 0
