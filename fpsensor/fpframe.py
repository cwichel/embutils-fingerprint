#!/usr/bin/python
# -*- coding: ascii -*-
"""
Fingerprint frame implementation.

@date:      2021
@author:    Christian Wiche
@contact:   cwichel@gmail.com
@license:   The MIT License (MIT)
"""

from dataclasses import dataclass
from embutils.serial.core import SerialDevice
from embutils.serial.data import Frame, FrameHandler
from embutils.utils import EventHook, IntEnumMod, ThreadItem
from typing import Union

from .fpapi import FpPID


@dataclass
class FpFrame(Frame):
    """Fingerprint frame definition.
    Data:
        0: Header   : 2 byte MSB    : 0   - 1
        1: Address  : 4 byte MSB    : 2   - 5
        2: PID      : 1 byte        : 6
        3: Length   : 2 byte MSB    : 7   - 8
        4: Data     : N byte        : 9   - N
        5: Checksum : 2 byte MSB    : N+1 - N+2

    Min size:  11   -> When data is empty.
    Max size: 265   -> Max (data + crc) length is 256.
    """
    LENGTH  = 9             # Set with minimum length
    HEADER  = 0xEF01        # Fixed frame header
    ADDRESS = 0xFFFFFFFF    # Default module address

    address:    int = ADDRESS
    pid:        FpPID = FpPID.COMMAND
    packet:     bytearray = bytearray()

    def __repr__(self) -> str:
        """Get the class representation string.

        Return:
            str: Class representation string.
        """
        return f'<{self.__class__.__name__}: address=0x{self.address:08X}, pid={self.pid.__repr__()}, packet=0x{self.packet.hex()}>'

    @property
    def checksum(self) -> int:
        """Checksum of the packet.

        Returns:
            int: Packet checksum.
        """
        return 0xFFFF & sum(self.raw())

    @property
    def length(self) -> int:
        """Packet length, by definition:
            len(packet) + len(checksum)

        Returns:
            int: Packet length.
        """
        return len(self.packet) + 2

    def raw(self) -> bytearray:
        """RAW data of the packet, defined as:
            PID + length + packet

        Returns:
            bytearray: Packet base data.
        """
        return bytearray(
            bytes([self.pid]) +
            self.length.to_bytes(length=2, byteorder='big', signed=False) +
            self.packet
            )

    def serialize(self) -> bytearray:
        """Convert the frame into a byte array.

        Returns:
            bytearray: Serialized frame.
        """
        return bytearray(
            self.HEADER.to_bytes(length=2, byteorder='big', signed=False) +
            self.address.to_bytes(length=4, byteorder='big', signed=False) +
            self.raw() +
            self.checksum.to_bytes(length=2, byteorder='big', signed=False)
            )

    @staticmethod
    def deserialize(data: bytearray) -> Union[None, 'FpFrame']:
        """Parse the frame from a byte array.

        Args:
            data (bytearray): received bytes.

        Returns:
            FpFrame: Parsed frame.
        """
        # Check minimum length
        if len(data) < FpFrame.LENGTH:
            return None

        # Check header
        head = int.from_bytes(bytes=data[0:2], byteorder='big', signed=False)
        if head != FpFrame.HEADER:
            return None

        # Check PID
        if not FpPID.has_value(value=data[6]):
            return None

        # Parse
        tmp = FpFrame(
            address=int.from_bytes(bytes=data[2:6], byteorder='big', signed=False),
            pid=FpPID(data[6]),
            packet=data[9:-2]
            )

        # Check consistency
        plen = int.from_bytes(bytes=data[7:9], byteorder='big', signed=False)
        csum = int.from_bytes(bytes=data[-2:], byteorder='big', signed=False)
        if (plen != tmp.length) or (csum != tmp.checksum):
            return None
        return tmp


class FpFrameHandler(FrameHandler):
    """Fingerprint frame serial handler.
    This class defines how to read the frames from the serial device.
    """
    class State(IntEnumMod):
        """Receive process states.
        """
        WAIT_HEAD   = 0x01      # Wait for the frame header to be detected
        WAIT_DATA   = 0x02      # Read the remaining data

    def __init__(self):
        """Class initialization.
        Initialize the reception state machine.
        """
        self._state = self.State.WAIT_HEAD
        self._recv  = bytearray()

    def read_process(self, serial_device: SerialDevice, emitter: EventHook) -> bool:
        """This method implements the frame reading state machine.
        Args:
            serial_device (bytearray): Device to read the frame bytes.
            emitter (EventHook): Event to be raised when a frame is received.
        Return:
            bool: True if operation is ok, false on serial device disconnection or reading issues.
        """
        if self._state == self.State.WAIT_HEAD:
            # Get bytes until the header appears...
            recv = serial_device.read_until(expected=FpFrame.HEADER.to_bytes(length=2, byteorder='big', signed=False))
            if recv is None:
                return False

            # Process bytes
            self._recv  = bytearray(recv[-2:])
            if self._recv:
                self._state = self.State.WAIT_DATA

        elif self._state == self.State.WAIT_DATA:
            # Get the next bytes until length
            recv = serial_device.read_until(size=7)
            if recv is None:
                self._restart()
                return False
            self._recv.extend(recv)

            # Define how many bytes to get and wait for them
            rlen = int.from_bytes(bytes=recv[-2:], byteorder='big', signed=False)
            recv = serial_device.read_until(size=rlen)
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
        """Restart the state machine.
        """
        self._state = self.State.WAIT_HEAD
        self._recv.clear()
