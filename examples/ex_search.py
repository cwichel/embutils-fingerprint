#!/usr/bin/python
# -*- coding: ascii -*-
"""
Example: Fingerprint capture and database search.

:date:      2021
:author:    Christian Wiche
:contact:   cwichel@gmail.com
:license:   The MIT License (MIT)
"""

# External ======================================


# Internal ======================================
from fpsensor.sdk import FpSDK
from fpsensor.api import FpBaudrate, FpBufferID, ADDRESS, PASSWORD

from examples.ex_utils import wait_finger_action


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

        # Repeat this until the image is detected correctly
        tries = 0
        while True:
            # Wait until finger press the sensor and capture
            wait_finger_action(sdk=sdk, press=False)
            wait_finger_action(sdk=sdk, press=True)
            sdk.image_capture()
            sdk.backlight(enable=False)

            # Convert the image
            recv = sdk.image_convert(buffer=FpBufferID.BUFFER_1)
            if not recv.succ:
                tries += 1
                if tries < 3:
                    print(f'Error when converting fingerprint image ({str(recv.code)}). Try again!')
                    continue
                else:
                    raise sdk.Exception(message=f'Unable to get a good image of the fingerprint', code=recv.code)
            break

        # Execute search
        recv = sdk.match_1_n(buffer=FpBufferID.BUFFER_1)
        if recv.index == -1:
            print(f'Fingerprint not found in database!')
        else:
            print(f'Found fingerprint at index #{recv.index} wit accuracy score of {recv.score}')

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
