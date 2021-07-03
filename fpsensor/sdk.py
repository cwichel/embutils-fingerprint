#!/usr/bin/python
# -*- coding: ascii -*-
"""
Fingerprint SDK implementation.

:date:      2021
:author:    Christian Wiche
:contact:   cwichel@gmail.com
:license:   The MIT License (MIT)
"""

# External ======================================
import time
from embutils.serial.core import SerialInterface
from embutils.utils import time_elapsed, LOG_SDK, EventHook, ThreadItem
from PIL import Image
from typing import Tuple, Union

# Internal ======================================
from .api import (
    ADDRESS, PASSWORD, NOTEPAD_COUNT, NOTEPAD_SIZE,
    FpCommand, FpError, FpPID, FpBufferID, FpParameterID, FpBaudrate, FpPacketSize, FpSecurity,
    FpSystemParameters,
    to_bytes, from_bytes
    )
from .frame import FpFrame, FpFrameHandler

# Definitions ===================================
logger_sdk = LOG_SDK.logger


# Data Structures ===============================
class FpSDK(SerialInterface):
    """
    Fingerprint command interface implementation.

    Available events:

    #.  **on_frame_received:** This event is emitted when a frame is received
        and deserialized from the serial device. Subscribe using callbacks with
        syntax::

            def <callback>(frame: Frame)

    #.  **on_port_reconnect:** This event is emitted when the system is able to
        reconnect to the configured port. Subscribe using callbacks with syntax::

            def <callback>()

    #.  **on_port_disconnect:** This event is emitted when the system gets
        disconnected from the configured serial port. Subscribe using callbacks
        with syntax::

            def <callback>()

    #.  **on_finger_detected:** This event is emitted when the finger press the
        sensor. The detection is only possible when if the sensor has the TOUT signal
        pin connected to the CTS pin on the serial adapter. Subscribe using callbacks
        with syntax::

            def <callback>()

    """
    #: Default response timeout
    RESPONSE_TIMEOUT_S  = 5.0

    #: Default finger detection
    DETECTION_PERIOD    = 0.3

    #: Default serial device settings
    SERIAL_SETTINGS = {
        'baudrate': 57600,
        'bytesize': 8,
        'stopbits': 1,
        'parity':   'N',
        'timeout':  0.1
        }

    class Exception(Exception):
        """
        Exception raised when an error handling the fingerprint is detected.
        """
        def __init__(self, message: str, error: FpError) -> None:
            """
            Class initialization.

            :param str message: Error message.
            :param FpError error: Error code.
            """
            self.error = error
            super(FpSDK.Exception, self).__init__(f'{str(error)}: {message}')

    def __init__(self,
                 address: int = ADDRESS, password: int = PASSWORD,
                 port: str = None, baudrate: int = 57600, looped: bool = False
                 ) -> None:
        """
        Class initialization.

        :param str address:     Device address.
        :param str password:    Device password.
        :param str port:        Serial port.
        :param int baudrate:    Serial baudrate.
        :param bool looped:     Enable test mode (with looped serial).

        :raise ValueError: Raise if address or password values are not in a valid range.
        """
        # Initialize static data
        self._caps = None

        # Check address and password
        self._addr = self._value_check(value=address)
        self._pass = self._value_check(value=password)

        # Adjust baudrate
        logger_sdk.info(f'Formatting baudrate...')
        baudrate = FpBaudrate.from_int(value=baudrate)
        self.SERIAL_SETTINGS['baudrate'] = baudrate.to_int()
        logger_sdk.info(f'Using: {str(baudrate)}')

        # Initialize serial interface
        super(FpSDK, self).__init__(frame_handler=FpFrameHandler(), port=port, looped=looped)

        # Set finger detection
        self.on_finger_detected = EventHook()
        self._state     = False
        self._period    = self.DETECTION_PERIOD
        self._detector  = ThreadItem(name=f'{self.__class__.__name__}.detector_process', target=self._detector_process)

    @property
    def address(self) -> int:
        """
        Device address.

        :return: Address.
        :rtype: int
        """
        return self._addr

    @address.setter
    def address(self, value: int) -> None:
        """
        Set device address.

        :param int value: Address.
        """
        succ, _ = self._value_set(command=FpCommand.ADDRESS_SET, value=value)
        if succ:
            self._addr = value

    @property
    def password(self) -> int:
        """
        Device password.

        :return: Password.
        :rtype: int
        """
        return self._pass

    @password.setter
    def password(self, value: int) -> None:
        """
        Set device password.

        :param int value: Password.
        """
        succ, _ = self._value_set(command=FpCommand.PASSWORD_SET, value=value)
        if succ:
            self._pass = value

    @property
    def capacity(self) -> int:
        """
        Device database capacity.

        :return: Capacity.
        :rtype: int
        """
        if self._caps is None:
            self._caps = self.parameters_get().capacity
        return self._caps

    @property
    def baudrate(self) -> FpBaudrate:
        """
        Device baudrate.

        :return: Baudrate.
        :rtype: FpBaudrate
        """
        return self.parameters_get().baudrate

    @baudrate.setter
    def baudrate(self, value: Union[int, FpBaudrate]) -> None:
        """
        Set device baudrate.

        :param Union[int, FpBaudrate] value: Baudrate.
        """
        self._parameter_set(param=FpParameterID.BAUDRATE, value=value)

    @property
    def security(self) -> FpSecurity:
        """
        Device security level.

        :return: Security level.
        :rtype: FpSecurity
        """
        return self.parameters_get().security

    @security.setter
    def security(self, value: Union[int, FpSecurity]) -> None:
        """
        Set device security level.

        :param Union[int, FpSecurity] value: Security level.
        """
        self._parameter_set(param=FpParameterID.SECURITY, value=value)

    @property
    def packet_size(self) -> FpPacketSize:
        """
        Device packet size.

        :return: Packet size.
        :rtype: FpPacketSize
        """
        return self.parameters_get().packet

    @packet_size.setter
    def packet_size(self, value: Union[int, FpPacketSize]) -> None:
        """
        Set device packet size.

        :param Union[int, FpPacketSize] value: Packet size.
        """
        self._parameter_set(param=FpParameterID.PACKET_SIZE, value=value)

    @property
    def period(self) -> float:
        """
        Get the finger detection period.

        :returns: Period in seconds.
        :rtype: float
        """
        return self._period

    @period.setter
    def period(self, value: float) -> None:
        """
        Get the finger detection period.

        :param float value: Detection period in seconds.
        """
        if value <= 0.0:
            raise ValueError('The detection period needs to be greater than zero.')
        self._period = value

    @property
    def is_finger(self) -> bool:
        """
        Returns if the finger is currently on the sensor.

        :return: True if finger on sensor, false otherwise.
        :rtype: bool
        """
        return self.frame_stream.serial_device.serial.cts

    def handshake(self) -> bool:
        """
        Performs a handshake with the sensor. This command is used to ensure the communication with the sensor is
        working correctly.

        :return: True if succeed, false otherwise.
        :rtype: bool
        """
        return self._command_set(command=FpCommand.HANDSHAKE)

    def backlight(self, enable: bool) -> bool:
        """
        Enables/disables the sensor backlight.

        :param bool enable: True to turn on, false to turn off.

        :return: True if succeed, false otherwise.
        :rtype: bool
        """
        return self._command_set(command=(FpCommand.BACKLIGHT_ON if enable else FpCommand.BACKLIGHT_OFF))

    def password_verify(self, password: int = None) -> bool:
        """
        Verifies the given password with the one set on sensor.

        .. note::
            If the sensor has a password this command needs to be used instead
            of the handshake.

        :param int password: Sensor password. If None, use the one provided on initialization.

        :return: True if verified, false otherwise.
        :rtype: bool
        """
        if password is None:
            password = self._pass

        password = to_bytes(value=self._value_check(value=password), size=4)
        return self._command_set(command=FpCommand.PASSWORD_VERIFY, packet=password)

    def parameters_get(self) -> FpSystemParameters:
        """
        Get the system parameters form the sensor.

        :return: Structure with parsed system parameters.
        :rtype: FpSystemParameters

        :raises FpSdk.Exception: Raise if an error is detected.
        """
        recv, _ = self._command_get(command=FpCommand.PARAMETERS_GET)
        return FpSystemParameters.deserialize(data=recv.packet[1:])

    def image_capture(self, free: bool = False) -> bool:
        """
        Captures an image of the fingerprint and stores it on the image buffer.

        :param bool free: If true try to capture without controlling the backlight.

        :return: True if capture was successful, false otherwise.
        :rtype: bool
        """
        return self._command_set(command=(FpCommand.IMAGE_CAPTURE_FREE if free else FpCommand.IMAGE_CAPTURE))

    def image_convert(self, buffer: Union[int, FpBufferID]) -> bool:
        """
        Converts the captured image and stores the result on the defined char buffer.

        :param Union[int, FpBufferID] buffer: Buffer ID.

        :return: True if conversion was successful, false otherwise.
        :rtype: bool
        """
        if not FpBufferID.has_value(value=buffer):
            raise ValueError(f'Buffer value not supported: {buffer}')

        return self._command_set(command=FpCommand.IMAGE_CONVERT, packet=bytearray([FpBufferID(buffer)]))

    def image_download(self) -> Image:
        """
        Downloads the fingerprint image from the image buffer.

        :return: Fingerprint image.
        :rtype: Image
        """
        # Get image bytes
        _, data = self._command_get(command=FpCommand.IMAGE_DOWNLOAD, data_wait=True)

        # Generate image
        image = Image.new(mode='L', size=(256, 288), color='white')
        pixel = image.load()
        w, h  = image.size

        # Populate image
        aux = w // 2
        for y in range(h):
            off = aux * y
            for x in range(aux):
                idx  = 2 * x
                byte = data[off + x]
                pixel[idx, y]       = (0x0F & (byte >> 4)) << 4
                pixel[(idx + 1), y] = (0x0F & byte) << 4

        return image

    def template_index(self) -> list:
        """
        Returns a list with the occupied indexes on the sensor database.

        :return: List of occupied indexes.
        :rtype: List[bool]
        """
        count = 0
        index = []
        pages = self._caps // 256
        for page in range(pages + 1):
            recv, _ = self._command_get(command=FpCommand.TEMPLATE_INDEX, packet=bytearray([page]))
            for byte in recv.packet[1:]:
                for bit in range(8):
                    index.append((byte & (1 << bit)) > 0)
                    count += 1
                    if count == self._caps:
                        return index

    def template_count(self) -> int:
        """
        Number of templates stored on the sensor database.

        :return: Number stored templates.
        :rtype: int
        """
        recv, _ = self._command_get(command=FpCommand.TEMPLATE_COUNT)
        return from_bytes(data=recv.packet[1:3])

    def template_create(self) -> bool:
        """
        Combines the contents of the char buffers into one template. The resulting template will be stored on both
        buffers.

        :return: True if succeed, false otherwise.
        :rtype: bool
        """
        return self._command_set(command=FpCommand.TEMPLATE_CREATE)

    def template_load(self, buffer: Union[int, FpBufferID], index: int = 0) -> bool:
        """
        Loads an existing template from the given database position into the specified char buffer.

        :param Union[int, FpBufferID] buffer: Buffer ID.
        :param int index: Position on the device database.

        :return: True if succeed, false otherwise.
        :rtype: bool
        """
        return self._template_manage(buffer=buffer, index=index, save=False)

    def template_save(self, buffer: Union[int, FpBufferID], index: int = 0) -> bool:
        """
        Saves a template from the specified char buffer at the given database position.

        :param Union[int, FpBufferID] buffer: Buffer ID.
        :param int index: Position on the device database.

        :return: True if succeed, false otherwise.
        :rtype: bool
        """
        return self._template_manage(buffer=buffer, index=index, save=True)

    def template_empty(self) -> bool:
        """
        Delete all the templates from the device database.

        :return: True if succeed, false otherwise.
        :rtype: bool
        """
        return self._command_set(command=FpCommand.TEMPLATE_EMPTY)

    def template_delete(self, index: int = 0, count: int = 1) -> bool:
        """
        Deletes a template from the device database. By default one.

        :param int index: Position on the device database.
        :param int count: Number of templates to be deleted.

        :return: True if succeed, false otherwise.
        :rtype: bool
        """
        if index < 0 or index >= self._caps:
            raise ValueError(f'Index exceeds device capacity: {index} > {self._caps}')
        if count < 0 or count > (self._caps - index):
            raise ValueError(f'The selection exceeds bounds: {index + count} > {self._caps}')

        pack = to_bytes(value=index, size=2) + to_bytes(value=count, size=2)
        return self._command_set(command=FpCommand.TEMPLATE_DELETE, packet=pack)

    def match_1_1(self) -> int:
        """
        Compare the contents stored in the char buffers and returns the accuracy score.

        :returns: Accuracy score.
        :rtype: int
        """
        recv, _ = self._command_get(command=FpCommand.TEMPLATE_MATCH)
        return from_bytes(data=recv.packet[1:3])

    def match_1_n(self, buffer: Union[int, FpBufferID], index: int = 0, count: int = None, fast: bool = False) -> Tuple[int, int]:
        """
        Searches the device database for the template in char buffer.

        :param Union[int, FpBufferID] buffer: Buffer ID.
        :param int index: Position on the device database.
        :param int count: Number of templates to be compared.
        :param bool fast: True to perform a fast search, false otherwise.

        :return: A tuple that contains: The position of the matching template (0) and the accuracy score (1).
        :rtype: Tuple[int, int]
        """
        if index < 0 or index >= self._caps:
            raise ValueError(f'Index exceeds device capacity: {index} > {self._caps}')
        if count < 0 or count > (self._caps - index):
            raise ValueError(f'The selection exceeds bounds: {index + count} > {self._caps}')
        if not FpBufferID.has_value(value=buffer):
            raise ValueError(f'Buffer value not supported: {buffer}')

        cmd  = FpCommand.TEMPLATE_SEARCH_FAST if fast else FpCommand.TEMPLATE_SEARCH
        pack = to_bytes(value=index, size=2) + to_bytes(value=count, size=2)
        recv, _ = self._command_get(command=cmd, packet=pack)

        return from_bytes(data=recv.packet[1:3]), from_bytes(data=recv.packet[3:5])

    def buffer_download(self, buffer: Union[int, FpBufferID]) -> bytearray:
        """
        Downloads the char buffer data.

        :param Union[int, FpBufferID] buffer: Buffer ID.

        :return: Buffer contents.
        :rtype: bytearray
        """
        if not FpBufferID.has_value(value=buffer):
            raise ValueError(f'{FpBufferID.__name__} value not supported: {buffer}')

        pack = bytearray([FpBufferID(buffer)])
        _, data = self._command_get(command=FpCommand.TEMPLATE_DOWNLOAD, packet=pack, data_wait=True)
        return data

    def buffer_upload(self, buffer: Union[int, FpBufferID], data: bytearray) -> bool:
        """
        Uploads data to the char buffer. After transmission this function verifies the contents of the buffer to ensure
        the successful transmission.

        :param Union[int, FpBufferID] buffer: Buffer ID.
        :param bytearray data: Data to be uploaded to the buffer.

        :return: Buffer contents.
        :rtype: bytearray
        """
        if not FpBufferID.has_value(value=buffer):
            raise ValueError(f'{FpBufferID.__name__} value not supported: {buffer}')
        if not data:
            raise ValueError(f'Data is empty')

        # Send and verify
        succ = self._command_set(command=FpCommand.TEMPLATE_UPLOAD, data=data)
        if succ:
            recv = self.buffer_download(buffer=buffer)
            return data == recv
        return succ

    def notepad_get(self, page: int) -> bytearray:
        """
        Get the selected notepad page contents.

        :param int page: Page number.

        :return: Notepad page data.
        :rtype: bytearray
        """
        if page < 0 or page >= NOTEPAD_COUNT:
            raise ValueError(f'Notepad page out of range: {0} <= {page} < {NOTEPAD_COUNT}')

        recv, _ = self._command_get(command=FpCommand.NOTEPAD_GET, packet=bytearray([page]))
        data = recv.packet[1:]
        if len(data) != NOTEPAD_SIZE:
            raise BufferError(f'Notepad size is not the expected: {len(data)} instead of {NOTEPAD_SIZE}')
        return data

    def notepad_set(self, page: int, data: bytearray) -> bool:
        """
        Set the selected notepad page contents.

        :param int page:        Page number.
        :param bytearray data:  Data to be written on the page.

        :return: True if succeed, false otherwise.
        :rtype: bool
        """
        if page < 0 or page >= NOTEPAD_COUNT:
            raise ValueError(f'Notepad page out of range: {0} <= {page} < {NOTEPAD_COUNT}')
        if len(data) > NOTEPAD_SIZE:
            logger_sdk.info(f'Cropping data to match the notepad page size: {len(data)} cropped to {NOTEPAD_SIZE}')
            data = data[:NOTEPAD_SIZE]

        pack = bytearray([page]) + data
        return self._command_set(command=FpCommand.NOTEPAD_SET, packet=pack)

    def notepad_clear(self, page: int) -> bool:
        """
        Clear the contents of the selected notepad page.

        :param int page: Page number.

        :return: True if succeed, false otherwise.
        :rtype: bool
        """
        return self.notepad_set(page=page, data=bytearray(NOTEPAD_SIZE * [0x00]))

    def random_get(self) -> int:
        """
        Generates a random 32-bit decimal number.

        :return: Generated random number.
        :rtype: int
        """
        recv, _ = self._command_get(command=FpCommand.GENERATE_RANDOM)
        return from_bytes(data=recv.packet[1:5])

    def _detector_process(self) -> None:
        """
        Pulls periodically the state of the TOUT signal connected to CTS. If the finger is detected then an event is
        emitted.
        """
        time_start = time.time()
        while True:
            if time_elapsed(start=time_start) > self._period:
                state = self.frame_stream.serial_device.serial.cts
                if state != self._state:
                    self._state = state
                    if self._state:
                        logger_sdk.info(f'Finger detected on sensor!')
                        self.on_finger_detected.emit()
                time_start = time.time()
            time.sleep(0.01)

    def _command_get(self, command: FpCommand, packet: bytearray = bytearray(), data_wait: bool = False) -> Tuple[FpFrame, bytearray]:
        """
        Use this function when need to get parameters / data from to the device.

        :param FpCommand command:   Command ID.
        :param bytearray packet:    Command packet.
        :param bool data_wait:      True if waiting for data, False otherwise.

        :return: A tuple that contains: The response frame (0) and a buffer with response data (1).
        :rtype: Tuple[FpFrame, bytearray]
        """
        data_ok = False
        data_buff = bytearray()
        time_start = time.time()

        def wait_ack_logic(sent: FpFrame, recv: FpFrame):
            """Wait for ACK. If waiting for data, enable reception process.
            """
            _ = sent
            is_ack = (recv.pid == FpPID.ACK)
            return is_ack

        def wait_data_logic(frame: FpFrame):
            """Wait for all data to be received.
            """
            nonlocal data_buff, data_ok, time_start
            is_data = (frame.pid == FpPID.DATA)
            is_end = (frame.pid == FpPID.END_OF_DATA)
            if is_data or is_end:
                time_start = time.time()
                data_buff.extend(frame.packet)
            if is_end:
                data_ok = True

        # Prepare data reception
        if data_wait:
            self.on_frame_received += wait_data_logic

        # Transmit frame
        send = FpFrame(address=self._addr, pid=FpPID.COMMAND, packet=bytearray([command]) + packet)
        resp = self.transmit(send=send, logic=wait_ack_logic)
        if not isinstance(resp, FpFrame):
            raise self.Exception(message='Unable to get the response packet', error=FpError.ERROR_PACKET_RECEPTION)

        # Check command response and errors
        if resp.pid != FpPID.ACK:
            raise self.Exception(message='The received packet is not an ACK!', error=FpError.ERROR_PACKET_FAULTY)

        code = FpError(resp.packet[0])
        if code == FpError.ERROR_PACKET_TRANSMISSION:
            raise self.Exception(message='Communication error!', error=code)
        elif code == FpError.ERROR_ADDRESS:
            raise self.Exception(message='The sensor address is wrong!', error=code)
        elif code == FpError.ERROR_PASSWORD_VERIFY:
            raise self.Exception(message='Password verification required!', error=code)

        # Wait for data if required
        if data_wait:
            time_start = time.time()
            while not data_ok and (time_elapsed(start=time_start) < self.RESPONSE_TIMEOUT_S):
                time.sleep(0.01)
            self.on_frame_received -= wait_data_logic
            if not data_ok:
                raise TimeoutError(f'Timeout while waiting for data.')

        # Check and return
        code = FpError(resp.packet[0])
        if not ((code == FpError.SUCCESS) or (code == FpError.HANDSHAKE_SUCCESS)):
            raise self.Exception(message=f'Transaction error', error=code)
        return resp, data_buff

    def _command_set(self, command: FpCommand, packet: bytearray = bytearray(), data: bytearray = bytearray()) -> bool:
        """
        Use this function when need to set parameters / data to the device.

        :param FpCommand command:   Command ID.
        :param bytearray packet:    Command packet.
        :param bytearray data:      If not empty this data will be sent after successful command.

        :return: True if succeed, false otherwise.
        :rtype: bool
        """
        # Send command
        recv, _ = self._command_get(command=command, packet=packet)
        code = FpError(recv.packet[0])
        succ = (code == FpError.SUCCESS) or (code == FpError.HANDSHAKE_SUCCESS)

        # Send data, if required
        if data and succ:
            data_size = len(data)
            pack_size = self.packet_size.to_int()
            pack_num  = (data_size // pack_size) + int((data_size % pack_size) > 0)

            end   = 0
            frame = FpFrame(address=self._addr, pid=FpPID.DATA)
            for idx in range(pack_num - 1):
                start = idx * pack_size
                end   = start + pack_size
                frame.packet = data[start:end]
                self.transmit(send=frame)

            frame.pid    = FpPID.END_OF_DATA
            frame.packet = data[end:]
            self.transmit(send=frame)

        return succ

    def _template_manage(self, buffer: Union[int, FpBufferID], index: int = 0, save: bool = True) -> bool:
        """
        Save/load a template to/from the device database.

        :param Union[int, FpBufferID] buffer: Buffer ID.
        :param int index: Position on the device database.
        :param bool save: If true, saves the template in the char buffer to the device database.

        :return: True if succeed, false otherwise.
        :rtype: bool
        """

        if index < 0 or index >= self._caps:
            raise ValueError(f'Index exceeds device capacity: {index} > {self._caps}')
        if not FpBufferID.has_value(value=buffer):
            raise ValueError(f'Buffer value not supported: {buffer}')

        cmd  = FpCommand.TEMPLATE_SAVE if save else FpCommand.TEMPLATE_LOAD
        pack = bytearray([FpBufferID(buffer)]) + to_bytes(value=index, size=2)
        return self._command_set(command=cmd, packet=pack)

    def _value_set(self, command: FpCommand, value: int) -> bool:
        """
        Set the selected command with the given value.

        :param FpCommand command: Command ID.
        :param int value: Value to set.

        :return: A tuple that contains: Operation status (0) and return code (1).
        :rtype: Tuple[bool, FpError]
        """
        value = to_bytes(value=self._value_check(value=value), size=2)
        return self._command_set(command=command, packet=value)

    def _parameter_set(self, param: FpParameterID, value: Union[int, FpBaudrate, FpPacketSize, FpSecurity]) -> bool:
        """
        Set the selected parameter with the given value.

        :param FpParameterID param: Parameter ID.
        :param Union[int, FpBaudrate, FpPacketSize, FpSecurity] value: Parameter setting.

        :return: True if succeed, false otherwise.
        :rtype: bool
        """
        # Get type
        _type = param.get_type()
        if not _type.has_value(value=value):
            raise ValueError(f'{_type.__name__} value not supported: {value}')

        # Perform operation
        value = _type(value)
        succ = self._command_set(command=FpCommand.PARAMETERS_SET, packet=bytearray([param, value]))
        if param != FpParameterID.BAUDRATE:
            return succ

        # Special case for baudrate
        if succ:
            logger_sdk.info(f'Updating serial baudrate to {str(value)}...')
            self.frame_stream.pause()
            self.frame_stream.serial_device.serial.baudrate = value.to_int()
            self.frame_stream.resume()
        return succ

    @staticmethod
    def _value_check(value: int) -> int:
        """
        Checks if the given value is in the address/password value range.

        :param int value: Integer to check.

        :return: Value if valid.
        :rtype: int

        :raise ValueError: Raise if value is not in valid range.
        """
        if value < 0x00000000 or 0xFFFFFFFF < value:
            raise ValueError(f'Value out of range (0x00000000 < 0x{value:08X} < 0xFFFFFFFF)!')
        return value
