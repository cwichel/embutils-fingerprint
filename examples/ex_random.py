#!/usr/bin/python
# -*- coding: ascii -*-
"""
Example: 32-bit random number generation.

:date:      2021
:author:    Christian Wiche
:contact:   cwichel@gmail.com
:license:   The MIT License (MIT)
"""

from embutils.utils import SDK_LOG

from fpsensor.sdk import FpSDK
from fpsensor.api import FpBaudrate

from examples.ex_utils import parse_args


# -->> Definitions <<------------------


# -->> Example <<----------------------
def example(sdk: FpSDK):
    try:
        # Tries to initialize the sensor
        recv = sdk.password_verify()
        if not recv.succ:
            raise sdk.Error(message='Error when trying to communicate with the device', code=recv.code)
        sdk.backlight(enable=False)

        # Tries to generate the random number
        recv = sdk.random_get()
        if not recv.succ:
            raise sdk.Error(message='Operation failed', code=recv.code)

        # Shows value
        print(f'Generated random value: {recv.value}')

    except Exception as info:
        # Prints the error string
        print(info)

    finally:
        # Stops the sensor gracefully
        sdk.stop()


# -->> Execution <<--------------------
if __name__ == '__main__':
    # Comment to disable logger
    SDK_LOG.enable()

    # Initialize the sensor and perform the example when gets connected
    port, addr, passwd = parse_args()
    fp = FpSDK(port=port, baudrate=FpBaudrate.BAUDRATE_57600, address=addr, password=passwd)
    fp.on_connect += lambda: example(sdk=fp)
    fp.join()
