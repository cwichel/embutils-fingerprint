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
from fpsensor.api import FpBaudrate, ADDRESS, PASSWORD

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

        # Wait until finger press the sensor and capture
        wait_finger_action(sdk=sdk, press=True)
        sdk.image_capture()
        sdk.backlight(enable=False)

        # Tries to download the image
        print(f'Image captured. Wait while the image is being downloaded...')
        recv = sdk.image_download()
        if not recv.succ:
            raise sdk.Exception(message=f'Error while retrieving the image', code=recv.code)

        # Show the image
        print(f'Image downloaded. Opening image now...')
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
    fp = FpSDK(port=FP_PORT, baudrate=FpBaudrate.BAUDRATE_57600, address=FP_ADDR, password=FP_PASS)
    fp.on_port_reconnect += lambda: example(sdk=fp)
    fp.join()
