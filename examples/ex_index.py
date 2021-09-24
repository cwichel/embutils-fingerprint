#!/usr/bin/python
# -*- coding: ascii -*-
"""
Example: Recover the fingerprint database index from the device.

:date:      2021
:author:    Christian Wiche
:contact:   cwichel@gmail.com
:license:   The MIT License (MIT)
"""

# External ======================================


# Internal ======================================
from fpsensor.sdk import FpSDK
from fpsensor.api import FpBaudrate

from examples.ex_utils import parse_args


# Tunables ======================================


# Definitions ===================================
def example(sdk: FpSDK):
    try:
        # Tries to initialize the sensor
        recv = sdk.password_verify()
        if not recv.succ:
            raise sdk.Error(message='Error when trying to communicate with the device', code=recv.code)
        sdk.backlight(enable=False)

        # Tries to get the index table
        recv = sdk.template_index()
        if not recv.succ:
            raise sdk.Error(message='Operation failed', code=recv.code)

        # Get used indexes list
        indexes = []
        for idx in range(sdk.capacity):
            if recv.value[idx]:
                indexes.append(idx)

        # Shows value
        print(f'Device info:\n'
              f'- Capacity      : {sdk.capacity}\n'
              f'- Used count    : {sdk.count}\n'
              f'- Used indexes  : {", ".join(f"{idx}" for idx in indexes)}')

    except Exception as info:
        # Prints the error string
        print(info)

    finally:
        # Stops the sensor gracefully
        sdk.stop()


# Execution =====================================
if __name__ == '__main__':
    # Initialize the sensor and perform the example when gets connected
    port, addr, passwd = parse_args()
    fp = FpSDK(port=port, baudrate=FpBaudrate.BAUDRATE_57600, address=addr, password=passwd)
    fp.on_connect += lambda: example(sdk=fp)
    fp.join()
