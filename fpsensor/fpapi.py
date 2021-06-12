#!/usr/bin/python
# -*- coding: ascii -*-
"""
Fingerprint API definitions.

@date:      2021
@author:    Christian Wiche
@contact:   cwichel@gmail.com
@license:   The MIT License (MIT)
"""

from dataclasses import dataclass
from embutils.utils import IntEnumMod, Serialized
from typing import Union


class FpPID(IntEnumMod):
    """Fingerprint packet ID.
    """
    COMMAND     = 0x01          # Command
    DATA        = 0x02          # Data
    ACK         = 0x07          # Acknowledge
    END_OF_DATA = 0x08          # End of data


class FpBufferID(IntEnumMod):
    """Fingerprint available buffers.
    """
    BUFFER_1    = 0x01
    BUFFER_2    = 0x02


class FpConfigID(IntEnumMod):
    """Fingerprint available configuration parameters
    """
    BAUDRATE        = 0x04
    SECURITY        = 0x05
    PACKET_LENGTH   = 0x06


class FpBaudrate(IntEnumMod):
    """Fingerprint available baudrates.
    """
    BAUDRATE_9600   = 0x01
    BAUDRATE_19200  = 0x02
    BAUDRATE_28800  = 0x03
    BAUDRATE_34800  = 0x04
    BAUDRATE_48000  = 0x05
    BAUDRATE_57600  = 0x06
    BAUDRATE_67200  = 0x07
    BAUDRATE_76800  = 0x08
    BAUDRATE_86400  = 0x09
    BAUDRATE_96000  = 0x0A
    BAUDRATE_105600 = 0x0B
    BAUDRATE_115200 = 0x0C


class FpSecurity(IntEnumMod):
    """Fingerprint available security levels.
    """
    SECURITY_LVL1   = 0x01
    SECURITY_LVL2   = 0x02
    SECURITY_LVL3   = 0x03
    SECURITY_LVL4   = 0x04
    SECURITY_LVL5   = 0x05


class FpPacketSize(IntEnumMod):
    """Fingerprint available packet sizes.
    """
    PACKET_SIZE_32  = 0x00
    PACKET_SIZE_64  = 0x01
    PACKET_SIZE_128 = 0x02
    PACKET_SIZE_256 = 0x03


class FpCommand(IntEnumMod):
    """Fingerprint commands ID.
    Notes:
        - The term "upload" is backwards on the documentation. Here it means from host to sensor.
        - The term "download" is backwards on the documentation. Here it means from sensor to host.
    """
    # System
    ADDRESS_SET             = 0x15
    PASSWORD_SET            = 0x12
    PASSWORD_VERIFY         = 0x13
    PARAMETERS_SET          = 0x0E
    PARAMETERS_GET          = 0x0F
    HANDSHAKE               = 0x53

    # Image
    IMAGE_CAPTURE           = 0x01
    IMAGE_CAPTURE_FREE      = 0x52
    IMAGE_CONVERT           = 0x02
    IMAGE_UPLOAD            = 0x0B
    IMAGE_DOWNLOAD          = 0x0A

    # Template
    TEMPLATE_MATCH          = 0x03
    TEMPLATE_SEARCH         = 0x04
    TEMPLATE_SEARCH_FAST    = 0x1B
    TEMPLATE_CREATE         = 0x05
    TEMPLATE_STORE          = 0x06
    TEMPLATE_LOAD           = 0x07
    TEMPLATE_UPLOAD         = 0x08
    TEMPLATE_DOWNLOAD       = 0x09
    TEMPLATE_DELETE         = 0x0C
    TEMPLATE_EMPTY          = 0x0D
    TEMPLATE_COUNT          = 0x1D
    TEMPLATE_INDEX_TABLE    = 0x1F

    # Extras
    NOTEPAD_SET             = 0x18
    NOTEPAD_GET             = 0x19
    GENERATE_RANDOM         = 0x14
    BACKLIGHT_ON            = 0x50
    BACKLIGHT_OFF           = 0x51


class FpError(IntEnumMod):
    """Fingerprint error ID.
    """
    SUCCESS                             = 0x00

    ERROR_INVALID_REGISTER              = 0x1A
    ERROR_INVALID_CONFIGURATION         = 0x1B

    ERROR_NOTEPAD_INVALID_PAGE          = 0x1C

    ERROR_PACKET_TRANSMISSION           = 0x01
    ERROR_PACKET_RECEPTION              = 0x0E
    ERROR_PACKET_FAULTY                 = 0xFE

    ERROR_FINGER_NOT_IN_SENSOR          = 0x02
    ERROR_FINGER_ENROLL_FAILED          = 0x03
    ERROR_FINGER_MISMATCH               = 0x08
    ERROR_FINGER_NOT_FOUND              = 0x09

    ERROR_IMAGE_MESSY                   = 0x06
    ERROR_IMAGE_INVALID                 = 0x15
    ERROR_IMAGE_FEW_FEATURE_POINTS      = 0x07
    ERROR_IMAGE_DOWNLOAD                = 0x0F

    ERROR_CHARACTERISTICS_MISMATCH      = 0x0A

    ERROR_TEMPLATE_INVALID_INDEX        = 0x0B
    ERROR_TEMPLATE_LOAD                 = 0x0C
    ERROR_TEMPLATE_DOWNLOAD             = 0x0D
    ERROR_TEMPLATE_DELETE               = 0x10
    ERROR_TEMPLATE_EMPTY                = 0x11

    ERROR_FLASH                         = 0x18
    ERROR_TIMEOUT                       = 0xFF
    ERROR_UNDEFINED                     = 0x19
    ERROR_COMMUNICATION_PORT            = 0x1D

    ERROR_ADDRESS                       = 0x20
    ERROR_PASSWORD                      = 0x13
    ERROR_PASSWORD_VERIFY               = 0x21


@dataclass
class FpPacketCommand(Serialized):
    """Packet definition for command transmission.
    Data:
        0: Command ID           : 1 byte    : 0
        1: Payload (optional)   : N byte    : 1 - N
    """
    LENGTH = 1

    command:    FpCommand
    payload:    bytearray

    def serialize(self) -> bytearray:
        return bytearray([self.command]) + self.payload

    @staticmethod
    def deserialize(data: bytearray) -> Union[None, 'FpPacketCommand']:
        # Check data size
        if len(data) < FpPacketCommand.LENGTH:
            return None
        # Return packet
        return FpPacketCommand(
            command=FpCommand(data[0]),
            payload=data
            )


@dataclass
class FpPacketData(Serialized):
    """Packet definition for data transmission.
    Data:
        0: Payload              : N byte    : 1 - N
    """
    LENGTH = 1

    payload:    bytearray

    def serialize(self) -> bytearray:
        return self.payload

    @staticmethod
    def deserialize(data: bytearray) -> Union[None, 'FpPacketData']:
        # Check data size
        if len(data) < FpPacketData.LENGTH:
            return None
        # Return packet
        return FpPacketData(payload=data)


@dataclass
class FpPacketAck(Serialized):
    """Packet definition for ACK transmission.
    Data:
        0: Error Code           : 1 byte    : 0
        1: Payload (optional)   : N byte    : 1 - N
    """
    LENGTH = 1

    error:      FpError
    payload:    bytearray

    def serialize(self) -> bytearray:
        return bytearray([self.error]) + self.payload

    @staticmethod
    def deserialize(data: bytearray) -> Union[None, 'FpPacketAck']:
        # Check data size
        if len(data) < FpPacketAck.LENGTH:
            return None
        # Return packet
        return FpPacketAck(
            error=FpError(data[0]),
            payload=data
            )


@dataclass
class FpSystemParameters(Serialized):
    """Fingerprint system parameters.
    Data:
        0: Status       : 2 byte MSB    : 0 - 1
        1: ID           : 2 byte MSB    : 2 - 3
        2: Lib. Size    : 2 byte MSB    : 4 - 5
        3: Security Lvl.: 2 byte MSB    : 6 - 7
        4: Address      : 4 byte MSB    : 8 - 11
        5: Pack. Size   : 2 byte MSB    : 12 - 13
        6: Baudrate     : 2 byte MSB    : 14 - 15
    """
    LENGTH = 16

    status:     int
    id:         int
    address:    int
    capacity:   int
    packet:     FpPacketSize
    security:   FpSecurity
    baudrate:   FpBaudrate

    def serialize(self) -> bytearray:
        return bytearray(
            self.status.to_bytes(length=2, byteorder='big', signed=False) +
            self.id.to_bytes(length=2, byteorder='big', signed=False) +
            self.capacity.to_bytes(length=2, byteorder='big', signed=False) +
            self.security.to_bytes(length=2, byteorder='big', signed=False) +
            self.address.to_bytes(length=4, byteorder='big', signed=False) +
            self.packet.to_bytes(length=2, byteorder='big', signed=False) +
            self.baudrate.to_bytes(length=2, byteorder='big', signed=False)
            )

    @staticmethod
    def deserialize(data: bytearray) -> Union[None, 'FpSystemParameters']:
        # Check data size
        if len(data) < FpSystemParameters.LENGTH:
            return None

        # Parse data
        _stat   = int.from_bytes(bytes=data[0:2], byteorder='big', signed=False)
        _id     = int.from_bytes(bytes=data[2:4], byteorder='big', signed=False)
        _cap    = int.from_bytes(bytes=data[4:6], byteorder='big', signed=False)
        _sec    = int.from_bytes(bytes=data[6:8], byteorder='big', signed=False)
        _addr   = int.from_bytes(bytes=data[8:12], byteorder='big', signed=False)
        _pack   = int.from_bytes(bytes=data[12:14], byteorder='big', signed=False)
        _baud   = int.from_bytes(bytes=data[14:16], byteorder='big', signed=False)

        # Check security
        if not FpSecurity.has_value(value=_sec):
            return None

        # Check packet size
        if not FpPacketSize.has_value(value=_baud):
            return None

        # Check baudrate
        if not FpBaudrate.has_value(value=_baud):
            return None

        # Parse
        return FpSystemParameters(
            status=(0x0F & _stat),
            id=_id,
            capacity=_cap,
            security=FpSecurity(_sec),
            address=_addr,
            packet=FpPacketSize(_pack),
            baudrate=FpBaudrate(_baud)
            )
