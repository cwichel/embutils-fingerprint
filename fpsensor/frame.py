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
from .api import ADDRESS, FpPID, to_bytes, from_bytes


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

        :return: Representation string.
        :rtype: str
        """
        return f'{self.__class__.__name__}(address=0x{self.address:08X}, pid={str(self.pid)}, packet=0x{self.packet.hex()})'

    @property
    def checksum(self) -> int:
        """
        Packet checksum. This value computes a checksum over the PID, length
        and packet data.

        :return: Packet checksum.
        :rtype: int
        """
        return 0xFFFF & sum(self.raw())

    @property
    def length(self) -> int:
        """
        Packet length. By definition: `len(packet) + len(checksum)`

        :return: Packet length.
        :rtype: int
        """
        return len(self.packet) + 2

    def raw(self) -> bytearray:
        """
        Raw frame packet data. This group was defined to ease the checksum
        computation. The contents are: PID, length and packet data.

        :return: Serialized packet bytes.
        :rtype: bytearray
        """
        return bytearray(
            bytes([self.pid]) +
            to_bytes(value=self.length, size=2) +
            self.packet
            )

    def serialize(self) -> bytearray:
        """
        Converts the frame into a byte array.

        :return: Serialized frame.
        :rtype: bytearray
        """
        return bytearray(
            to_bytes(value=self.HEADER, size=2) +
            to_bytes(value=self.address, size=4) +
            self.raw() +
            to_bytes(value=self.checksum, size=2)
            )

    @staticmethod
    def deserialize(data: bytearray) -> Union[None, 'FpFrame']:
        """
        Parses the frame from a byte array.

        :param bytearray data: Bytes to be parsed.

        :return: None if deserialization fail, deserialized object otherwise.
        :rtype: FpFrame
        """
        # Check minimum length
        if len(data) < FpFrame.LENGTH:
            return None

        # Check frame fixed header
        head = from_bytes(data=data[0:2])
        if head != FpFrame.HEADER:
            return None

        # Check message PID
        if not FpPID.has_value(value=data[6]):
            return None

        # Parse frame bytes
        tmp = FpFrame(
            address=from_bytes(data=data[2:6]),
            pid=FpPID(data[6]),
            packet=data[9:-2]
            )

        # Check consistency using CRC
        plen = from_bytes(data=data[7:9])
        csum = from_bytes(data=data[-2:])
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
        WAIT_BASE   = 0x02      # Wait for frame length
        WAIT_DATA   = 0x03      # Wait for remaining data

    def __init__(self):
        """
        This class don't require any input from the user to be initialized.
        """
        self._count = 0
        self._state = self.State.WAIT_HEAD
        self._recv  = bytearray()

    def read_process(self, serial: SerialDevice, emitter: EventHook) -> bool:
        """
        This method implements the frame reading process.

        :param SerialDevice serial: Serial device from where the bytes are read.
        :param EventHook emitter:   Event to be raised when a frame is received.

        :return: True if success, false on serial device disconnection or reading issues.
        :rtype: bool
        """
        # Get all the available data and put it into the receive buffer
        recv = serial.read(size=serial.serial.in_waiting if serial.is_open else 1)
        if recv is None:
            return False
        self._recv.extend(recv)

        # Process received bytes
        while True:
            # Don't continue if we dont have at least the minimum frame length
            if len(self._recv) < FpFrame.LENGTH:
                break

            elif self._state == self.State.WAIT_HEAD:
                # Find the header and set it as start
                index = self._recv.find(to_bytes(value=FpFrame.HEADER, size=2))
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
                self._count = FpFrame.LENGTH + tmp - 2
                self._state = self.State.WAIT_DATA

            elif self._state == self.State.WAIT_DATA:
                # Wait for frame bytes
                if len(self._recv) < self._count:
                    break
                # Parse frame and emit (if possible)
                frame = FpFrame.deserialize(data=self._recv[0:self._count])
                if frame:
                    ThreadItem(name=f'{self.__class__.__name__}.on_frame_received', target=lambda: emitter.emit(frame=frame))
                    self._recv = self._recv[self._count:]
                else:
                    self._recv = self._recv[2:]
                self._restart()

            else:
                # Shouldn't be here...
                self._restart()
                break

        # Return status
        return True

    def _restart(self) -> None:
        """
        Restarts the frame handler state machine.
        """
        self._state = self.State.WAIT_BASE
        self._count = 0
