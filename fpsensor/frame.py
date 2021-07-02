#!/usr/bin/python
# -*- coding: ascii -*-
"""
Fingerprint frame.

@date:      2021
@author:    Christian Wiche
@contact:   cwichel@gmail.com
@license:   The MIT License (MIT)
"""

# External ======================================
from dataclasses import dataclass
from embutils.serial.core import SerialDevice
from embutils.serial.data import Frame, FrameHandler
from embutils.utils import EventHook, IntEnumMod, ThreadItem
from typing import Union

# Internal ======================================
from .api import ADDRESS, FpPID


# Definitions ===================================


# Data Structures ===============================
@dataclass
class FpFrame(Frame):
    """
    Fingerprint frame structure definition.

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
    #: Frame minimum length (header, address, PID, length and checksum).
    LENGTH  = 11
    #: Fixed frame header
    HEADER  = 0xEF01

    #: Device address
    address:    int = ADDRESS
    #: Frame type (PID)
    pid:        FpPID = FpPID.COMMAND
    #: Packet data
    packet:     bytearray = bytearray()

    def __repr__(self) -> str:
        """
        Representation string.

        :returns: Representation string.
        :rtype: str
        """
        return f'{self.__class__.__name__}(address=0x{self.address:08X}, pid={str(self.pid)}, packet=0x{self.packet.hex()})'

    @property
    def checksum(self) -> int:
        """
        Packet checksum. This value computes a checksum over the PID, length
        and packet data.

        :returns: Packet checksum.
        :rtype: int
        """
        return 0xFFFF & sum(self.raw())

    @property
    def length(self) -> int:
        """
        Packet length. By definition: `len(packet) + len(checksum)`

        :returns: Packet length.
        :rtype: int
        """
        return len(self.packet) + 2

    def raw(self) -> bytearray:
        """
        Raw frame packet data. This group was defined to ease the checksum
        computation. The contents are: PID, length and packet data.

        :returns: Serialized packet bytes.
        :rtype: bytearray
        """
        return bytearray(
            bytes([self.pid]) +
            self.length.to_bytes(length=2, byteorder='big', signed=False) +
            self.packet
            )

    def serialize(self) -> bytearray:
        """
        Converts the frame into a byte array.

        :returns: Serialized frame.
        :rtype: bytearray
        """
        return bytearray(
            self.HEADER.to_bytes(length=2, byteorder='big', signed=False) +
            self.address.to_bytes(length=4, byteorder='big', signed=False) +
            self.raw() +
            self.checksum.to_bytes(length=2, byteorder='big', signed=False)
            )

    @staticmethod
    def deserialize(data: bytearray) -> Union[None, 'FpFrame']:
        """
        Parses the frame from a byte array.

        :param bytearray data: Bytes to be parsed.

        :returns: None if deserialization fail, deserialized object otherwise.
        :rtype: FpFrame
        """
        # Check minimum length
        if len(data) < FpFrame.LENGTH:
            return None

        # Check frame fixed header
        head = int.from_bytes(bytes=data[0:2], byteorder='big', signed=False)
        if head != FpFrame.HEADER:
            return None

        # Check message PID
        if not FpPID.has_value(value=data[6]):
            return None

        # Parse frame bytes
        tmp = FpFrame(
            address=int.from_bytes(bytes=data[2:6], byteorder='big', signed=False),
            pid=FpPID(data[6]),
            packet=data[9:-2]
            )

        # Check consistency using CRC
        plen = int.from_bytes(bytes=data[7:9], byteorder='big', signed=False)
        csum = int.from_bytes(bytes=data[-2:], byteorder='big', signed=False)
        if (plen != tmp.length) or (csum != tmp.checksum):
            return None
        return tmp


class FpFrameHandler(FrameHandler):
    """
    Fingerprint frame serial handler. This class defines how to read the bytes
    from the serial device in order to deserialize frames.
    """
    class State(IntEnumMod):
        """
        Serial read process states.
        """
        WAIT_HEAD   = 0x01      # Wait for the frame header to be detected
        WAIT_DATA   = 0x02      # Read the remaining data

    def __init__(self):
        """
        This class don't require any input from the user to be initialized.
        """
        self._state = self.State.WAIT_HEAD
        self._recv  = bytearray()

    def read_process(self, serial: SerialDevice, emitter: EventHook) -> bool:
        """
        This method implements the frame reading process.

        :param SerialDevice serial: Serial device from where the bytes are read.
        :param EventHook emitter:   Event to be raised when a frame is received.

        :returns: True if success, false on serial device disconnection or reading issues.
        :rtype: bool
        """
        if self._state == self.State.WAIT_HEAD:
            # Get bytes until the header appears...
            recv = serial.read_until(expected=FpFrame.HEADER.to_bytes(length=2, byteorder='big', signed=False))
            if recv is None:
                return False

            # Process bytes
            self._recv  = bytearray(recv[-2:])
            if self._recv:
                self._state = self.State.WAIT_DATA

        elif self._state == self.State.WAIT_DATA:
            # Get the next bytes until length
            recv = serial.read_until(size=7)
            if recv is None:
                self._restart()
                return False
            self._recv.extend(recv)

            # Define how many bytes to get and wait for them
            rlen = int.from_bytes(bytes=recv[-2:], byteorder='big', signed=False)
            recv = serial.read_until(size=rlen)
            if recv is None:
                self._restart()
                return False
            self._recv.extend(recv)

            # Parse frame and emit
            frame = FpFrame.deserialize(data=self._recv)
            if frame:
                ThreadItem(name=f'{self.__class__.__name__}.on_frame_received', target=lambda: emitter.emit(frame=frame))
            self._restart()

        else:
            # Shouldn't be here...
            self._restart()

        # Return status
        return True

    def _restart(self) -> None:
        """
        Restarts the frame handler state machine.
        """
        self._state = self.State.WAIT_HEAD
        self._recv.clear()
