#!/usr/bin/python
# -*- coding: ascii -*-
"""
Example utilities. Not meant to be executed.

:date:      2021
:author:    Christian Wiche
:contact:   cwichel@gmail.com
:license:   The MIT License (MIT)
"""

# External ======================================
import time

# Internal ======================================
from fpsensor.sdk import FpSDK


# Tunables ======================================


# Definitions ===================================
def wait_finger_action(sdk: FpSDK, press: bool) -> None:
    """
    Wait until the required action is performed.

    :param FpSDK sdk:   Fingerprint SDK object.
    :param bool press:  True if finger press required, False otherwise.
    """
    # Check if we need to wait
    if press == sdk.finger_pressed:
        return

    # Execute wait logic
    ready = False

    def wait_action() -> None:
        nonlocal ready, press
        ready = (press == sdk.finger_pressed)

    if press:
        print(f'Wait for finger...')
        sdk.on_finger_pressed  += wait_action
    else:
        print(f'Remove finger from sensor...')
        sdk.on_finger_released += wait_action

    # Wait until action...
    while not ready:
        time.sleep(0.01)
