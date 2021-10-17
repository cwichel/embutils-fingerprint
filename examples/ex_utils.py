#!/usr/bin/python
# -*- coding: ascii -*-
"""
Example utilities. Not meant to be executed.

:date:      2021
:author:    Christian Wiche
:contact:   cwichel@gmail.com
:license:   The MIT License (MIT)
"""

import argparse as ap
import time

from typing import Tuple

from fpsensor.sdk import FpSDK
from fpsensor.api import ADDRESS, PASSWORD


# -->> Definitions <<------------------


# -->> API <<--------------------------
def parse_args() -> Tuple[str, int, int]:
    """
    Parses the port, address and password for the examples

    :return: Port, address, password
    :rtype: Tuple[str, int, int]
    """
    parser = ap.ArgumentParser()
    parser.add_argument('port', type=str, help='Device serial port, ex: COM3')
    parser.add_argument('-a', '--addr', type=str, default=None, required=False, help='Device address in HEX')
    parser.add_argument('-p', '--pass', type=str, default=None, required=False, help='Device password in HEX')
    args, unknown = parser.parse_known_args()

    addr = ADDRESS
    if args.addr:
        addr = int(args.addr, 16)

    passwd = PASSWORD
    if args.addr:
        passwd = int(args.addr, 16)

    return args.port, addr, passwd


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
