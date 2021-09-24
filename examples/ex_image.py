#!/usr/bin/python
# -*- coding: ascii -*-
"""
Example: Fingerprint image generation and download.

:date:      2021
:author:    Christian Wiche
:contact:   cwichel@gmail.com
:license:   The MIT License (MIT)
"""

# External ======================================


# Internal ======================================
from fpsensor.sdk import FpSDK
from fpsensor.api import FpBaudrate

from examples.ex_utils import parse_args, wait_finger_action


# Tunables ======================================


# Definitions ===================================
def example(sdk: FpSDK):
    try:
        # Tries to initialize the sensor
        recv = sdk.password_verify()
        if not recv.succ:
            raise sdk.Error(message='Error when trying to communicate with the device', code=recv.code)
        sdk.backlight(enable=False)

        # Wait until finger press the sensor and capture
        wait_finger_action(sdk=sdk, press=True)
        sdk.image_capture()
        sdk.backlight(enable=False)

        # Tries to download the image
        print('Image captured. Wait while the image is being downloaded...')
        recv = sdk.image_download()
        if not recv.succ:
            raise sdk.Error(message='Error while retrieving the image', code=recv.code)

        # Show the image
        print('Image downloaded. Opening image now...')
        recv.value.show()

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
