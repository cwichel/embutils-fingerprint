#!/usr/bin/python
# -*- coding: ascii -*-
"""
Example: Fingerprint capture and enroll.

:date:      2021
:author:    Christian Wiche
:contact:   cwichel@gmail.com
:license:   The MIT License (MIT)
"""

from embutils.utils import SDK_LOG

from fpsensor.sdk import FpSDK
from fpsensor.api import FpBaudrate, FpBufferID

from examples.ex_utils import parse_args, wait_finger_action


# -->> Definitions <<------------------


# -->> Example <<----------------------
def example(sdk: FpSDK):
    try:
        # Tries to initialize the sensor
        recv = sdk.password_verify()
        if not recv.succ:
            raise sdk.Error(message='Error when trying to communicate with the device', code=recv.code)
        sdk.backlight(enable=False)

        # Repeat this until both fingerprints are detected correctly
        tries  = 0
        buffer = FpBufferID.BUFFER_1
        while True:
            # Wait until finger press the sensor and capture
            wait_finger_action(sdk=sdk, press=False)
            wait_finger_action(sdk=sdk, press=True)
            sdk.image_capture()
            sdk.backlight(enable=False)

            # Convert the image
            recv = sdk.image_convert(buffer=buffer)
            if not recv.succ:
                tries += 1
                if tries >= 3:
                    raise sdk.Error(message='Unable to get a good image of the fingerprint', code=recv.code)
                print(f'Error when converting fingerprint image ({str(recv.code)}). Try again!')
                continue
            tries = 0

            # Continue depending on buffer
            if buffer == FpBufferID.BUFFER_1:
                # Check that finger is not registered
                recv = sdk.match_1_n(buffer=buffer)
                if recv.index != -1:
                    raise ValueError(f'Finger already registered on index #{recv.index}')
                buffer = FpBufferID.BUFFER_2

            elif buffer == FpBufferID.BUFFER_2:
                # Check that fingers match
                recv = sdk.match_1_1()
                if not recv.succ:
                    tries += 1
                    if tries >= 3:
                        raise RuntimeError('Fingers didnt match several times')
                    print('Fingers dont match. Try again!')
                    continue
                break

        # Generate template
        recv = sdk.template_create()
        if not recv.succ:
            raise sdk.Error(message='Template creation failed', code=recv.code)

        # Store the template
        recv = sdk.template_save(buffer=buffer)
        if not recv.succ:
            raise sdk.Error(message='Template store failed', code=recv.code)
        print(f'Fingerprint stored successfully on index #{recv.value}')

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
