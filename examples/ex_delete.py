#!/usr/bin/python
# -*- coding: ascii -*-
"""
Example: Fingerprint template deletion from device database.

:date:      2021
:author:    Christian Wiche
:contact:   cwichel@gmail.com
:license:   The MIT License (MIT)
"""

# External ======================================


# Internal ======================================
from fpsensor.sdk import FpSDK
from fpsensor.api import FpBaudrate, ADDRESS, PASSWORD


# Tunables ======================================
FP_PORT = 'COM15'
FP_ADDR = ADDRESS
FP_PASS = PASSWORD


# Definitions ===================================
def example(sdk: FpSDK):
    try:
        # Tries to initialize the sensor
        recv = sdk.password_verify()
        if not recv.succ:
            raise sdk.Exception(message=f'Error when trying to communicate with the device', code=recv.code)
        sdk.backlight(enable=False)

        # Ask the user for the template to delete
        index = int(input(f'Please enter the index of the template to be deleted: '))

        # Tries to delete the requested template
        recv = sdk.template_delete(index=index, count=1)
        if not recv.succ:
            raise sdk.Exception(message=f'Operation failed', code=recv.code)
        print(f'Template deleted!')

    except Exception as info:
        # Prints the error string
        print(info)

    finally:
        # Stops the sensor gracefully
        sdk.stop()


# Execution =====================================
if __name__ == '__main__':
    # Initialize the sensor and perform the example when gets connected
    fp = FpSDK(port=FP_PORT, baudrate=FpBaudrate.BAUDRATE_57600, address=FP_ADDR, password=FP_PASS)
    fp.on_port_reconnect += lambda: example(sdk=fp)
    fp.join()
