#!/usr/bin/python
# -*- coding: ascii -*-
"""
Fingerprint API definitions.

@date:      2021
@author:    Christian Wiche
@contact:   cwichel@gmail.com
@license:   The MIT License (MIT)
"""

from embutils.utils import IntEnumMod


class FpPID(IntEnumMod):
    """Fingerprint packet ID.
    """
    COMMAND     = 0x01          # Command
    DATA        = 0x02          # Data
    ACK         = 0x07          # Acknowledge
    END_OF_DATA = 0x08          # End of data


class FpCommands(IntEnumMod):
    """Fingerprint commands ID.
    Notes:
        - The term "upload" is backwards on the documentation. Here it means from host to sensor.
        - The term "download" is backwards on the documentation. Here it means from sensor to host.
    """
    IMAGE_CAPTURE           = 0x01
    IMAGE_CAPTURE_FREE      = 0x52
    IMAGE_CONVERT           = 0x02
    IMAGE_UPLOAD            = 0x0B
    IMAGE_DOWNLOAD          = 0x0A

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
    TEMPLATE_NUMBER         = 0x1D
    TEMPLATE_INDEX          = 0x1F

    SYSTEM_SET_PARAMETERS   = 0x0E
    SYSTEM_GET_PARAMETERS   = 0x0F

    PASSWORD_SET            = 0x12
    PASSWORD_VERIFY         = 0x13

    ADDRESS_SET             = 0x15

    NOTEPAD_SET             = 0x18
    NOTEPAD_GET             = 0x19

    BACKLIGHT_ON            = 0x50
    BACKLIGHT_OFF           = 0x51

    HANDSHAKE               = 0x53


class FpErrorCode(IntEnumMod):
    """Fingerprint error ID.
    """
    SUCCESS                             = 0x00

    ERROR_SYSTEM_INVALID_REGISTER       = 0x1A
    ERROR_SYSTEM_INVALID_CONFIGURATION  = 0x1B

    ERROR_NOTEPAD_INVALID_PAGE          = 0x1C

    ERROR_PACKET_TRANSMISSION           = 0x01
    ERROR_PACKET_MODULE_RECEPTION       = 0x0E
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
    ERROR_PASSWORD                      = 0x21






