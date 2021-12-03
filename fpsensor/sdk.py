#!/usr/bin/python
# -*- coding: ascii -*-
"""
Fingerprint SDK implementation.

:date:      2021
:author:    Christian Wiche
:contact:   cwichel@gmail.com
:license:   The MIT License (MIT)
"""

import time
import typing as tp

import PIL.Image as PilI
import embutils.serial as embs
import embutils.utils as embu

from .api import (
    ADDRESS, PASSWORD, NOTEPAD_COUNT, NOTEPAD_SIZE,
    FpCommand, FpError, FpPID, FpBufferID, FpParameterID, FpBaudrate, FpPacketSize, FpSecurity,
    FpSystemParameters, FpResponseSet, FpResponseGet, FpResponseMatch, FpResponseValue,
    to_bytes, from_bytes
    )
from .packet import FpPacket, FpStreamFramingCodec

# -->> Definitions <<------------------


# -->> API <<--------------------------
class FpSDK(embs.Interface):
    """
    Fingerprint command interface implementation.

    Available events:

    #.  **on_received:** This event is emitted when an object is received and
        deserialized from the serial device. Subscribe using callbacks with
        syntax::

            def <callback>(item: AbstractSerialized)

    #.  **on_connect:** This event is emitted when the system is able to
        connect to the device. Subscribe using callbacks with syntax::

            def <callback>()

    #.  **on_reconnect:** This event is emitted when the system is able to
        reconnect to the device. Subscribe using callbacks with syntax::

            def <callback>()

    #.  **on_disconnect:** This event is emitted when the system gets
        disconnected from the device. Subscribe using callbacks with syntax::

            def <callback>()

    #.  **on_finger_pressed:** This event is emitted when the finger press the
        sensor. Subscribe using callbacks with syntax::

            def <callback>()

    #.  **on_finger_released:** This event is emitted when the finger releases the
        sensor. Subscribe using callbacks with syntax::

            def <callback>()

    """
    #: Default response timeout
    TIMEOUT_RESPONSE_S  = 5.0

    #: Default finger detection
    PERIOD_DETECTION    = 0.3

    #: Default serial device settings
    SERIAL_SETTINGS = {
        'baudrate': 57600,
        'bytesize': 8,
        'stopbits': 1,
        'parity':   'N',
        'timeout':  0.1
        }

    class Error(Exception):
        """
        Issue appeared when handling the fingerprint device.
        """
        def __init__(self, message: str, code: FpError) -> None:
            """
            Class initialization.

            :param str message: Error message.
            :param FpError code: Error code.
            """
            self.error = code
            super(FpSDK.Error, self).__init__(f'{str(code)}: {message}')

    def __init__(self,
                 port: str = None, baudrate: int = None, looped: bool = False,
                 address: int = ADDRESS, password: int = PASSWORD,
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
        # Public events
        self.on_finger_pressed  = embu.EventHook()
        self.on_finger_released = embu.EventHook()

        # Initialize static data
        self._caps = None

        # Check address and password
        self._addr = self._auth_check(value=address)
        self._pass = self._auth_check(value=password)

        # Adjust baudrate
        settings = self.SERIAL_SETTINGS.copy()
        if baudrate:
            embu.SDK_LOG.info('Formatting baudrate...')
            baudrate = FpBaudrate.from_int(value=baudrate)
            settings['baudrate'] = baudrate.to_int()
            embu.SDK_LOG.info(f'Using: {str(baudrate)}')

        # Initialize serial interface
        sd = embs.Device(port=port, looped=looped, settings=settings)
        ss = embs.Stream(device=sd, codec=FpStreamFramingCodec())
        super().__init__(stream=ss)

        # Detector specific
        self._df_state     = False
        self._df_is_active = True
        self._df_period    = self.PERIOD_DETECTION
        self._df_finished  = False
        embu.SDK_TP.enqueue(task=embu.SimpleThreadTask(
            name=f'{self.__class__.__name__}.detector_process',
            task=self._detector_process
            ))

    def stop(self) -> None:
        """
        Stops the stream process.
        """
        # Stop detector
        self._df_is_active = False
        while not self._df_finished:
            time.sleep(0.01)
        # Stop serial
        super().stop()

    @property
    def period(self) -> float:
        """
        Finger detection period.
        """
        return self._df_period

    @period.setter
    def period(self, value: float) -> None:
        """
        Finger detection period setter.
        """
        if value <= 0.0:
            raise ValueError('The detection period needs to be greater than zero.')
        self._df_period = value

    @property
    def finger_pressed(self) -> bool:
        """
        Returns if the finger is currently pressing the sensor.
        """
        if self.stream.device.is_open:
            return self.stream.device.serial.cts
        return False

    @property
    def address(self) -> int:
        """
        Device address.
        """
        return self._addr

    @address.setter
    def address(self, value: int) -> None:
        """
        Device address setter.
        """
        recv = self._value_set(command=FpCommand.ADDRESS_SET, value=value)
        if recv.succ:
            self._addr = value
        else:
            raise self.Error(code=recv.code, message='Unable to set device address.')

    @property
    def password(self) -> int:
        """
        Device password.
        """
        return self._pass

    @password.setter
    def password(self, value: int) -> None:
        """
        Device password setter.
        """
        recv = self._value_set(command=FpCommand.PASSWORD_SET, value=value)
        if recv.succ:
            self._pass = value
        else:
            raise self.Error(code=recv.code, message='Unable to set device password.')

    @property
    def count(self) -> int:
        """
        Number of slots being used on the device database.
        """
        recv = self._command_get(command=FpCommand.TEMPLATE_COUNT)
        if recv.succ:
            return from_bytes(data=recv.pack[0:2])
        raise self.Error(code=recv.code, message='Unable to get device usage.')

    @property
    def capacity(self) -> int:
        """
        Number of slots on the device database.
        """
        if self._caps is None:
            recv = self.parameters_get()
            if recv.succ:
                self._caps = recv.value.capacity
            else:
                raise self.Error(code=recv.code, message='Unable to get device capacity.')
        return self._caps

    @property
    def baudrate(self) -> FpBaudrate:
        """
        Device baudrate.
        """
        recv = self.parameters_get()
        if recv.succ:
            return recv.value.baudrate
        raise self.Error(code=recv.code, message='Unable to get device baudrate.')

    @baudrate.setter
    def baudrate(self, value: tp.Union[int, FpBaudrate]) -> None:
        """
        Device baudrate setter.
        """
        recv = self._parameter_set(param=FpParameterID.BAUDRATE, value=value)
        if not recv.succ:
            raise self.Error(code=recv.code, message=f'Unable to set baudrate ({FpBaudrate(value)}).')

    @property
    def security(self) -> FpSecurity:
        """
        Device security level.
        """
        recv = self.parameters_get()
        if recv.succ:
            return recv.value.security
        raise self.Error(code=recv.code, message='Unable to get device security.')

    @security.setter
    def security(self, value: tp.Union[int, FpSecurity]) -> None:
        """
        Device security level setter.
        """
        recv = self._parameter_set(param=FpParameterID.SECURITY, value=value)
        if not recv.succ:
            raise self.Error(code=recv.code, message=f'Unable to set security ({FpSecurity(value)}).')

    @property
    def packet_size(self) -> FpPacketSize:
        """
        Device packet size.
        """
        recv  = self.parameters_get()
        if recv.succ:
            return recv.value.packet
        raise self.Error(code=recv.code, message='Unable to get packet size.')

    @packet_size.setter
    def packet_size(self, value: tp.Union[int, FpPacketSize]) -> None:
        """
        Device packet size setter.
        """
        recv = self._parameter_set(param=FpParameterID.PACKET_SIZE, value=value)
        if not recv.succ:
            raise self.Error(code=recv.code, message=f'Unable to set packet size ({FpPacketSize(value)}).')

    def handshake(self) -> FpResponseSet:
        """
        Performs a handshake with the sensor. This command is used to ensure the communication with the sensor is
        working correctly.

        :return: Fingerprint set response.
        :rtype: FpResponseSet
        """
        return self._command_set(command=FpCommand.HANDSHAKE)

    def backlight(self, enable: bool) -> FpResponseSet:
        """
        Enables/disables the sensor backlight.

        :param bool enable: True to turn on, false to turn off.

        :return: Fingerprint set response.
        :rtype: FpResponseSet
        """
        return self._command_set(command=(FpCommand.BACKLIGHT_ON if enable else FpCommand.BACKLIGHT_OFF))

    def password_verify(self, password: int = None) -> FpResponseSet:
        """
        Verifies the given password with the one set on sensor.

        .. note::
            If the sensor has a password this command needs to be used instead
            of the handshake.

        :param int password: Sensor password. If None, use the one provided on initialization.

        :return: Fingerprint set response.
        :rtype: FpResponseSet
        """
        if password is None:
            password = self._pass

        password = to_bytes(value=self._auth_check(value=password), size=4)
        return self._command_set(command=FpCommand.PASSWORD_VERIFY, packet=password)

    def parameters_get(self) -> FpResponseValue:
        """
        Get the system parameters form the sensor.

        :return: Fingerprint value response.
        :rtype: FpResponseValue

        :raises FpSdk.Exception: Raise if an error is detected.
        """
        recv   = self._command_get(command=FpCommand.PARAMETERS_GET)
        params = None
        if recv.succ:
            params = FpSystemParameters.deserialize(data=recv.pack)
        return FpResponseValue(succ=recv.succ, code=recv.code, value=params)

    def image_capture(self, free: bool = False) -> FpResponseSet:
        """
        Captures an image of the fingerprint and stores it on the image buffer.

        :param bool free: If true try to capture without controlling the backlight.

        :return: Fingerprint set response.
        :rtype: FpResponseSet
        """
        return self._command_set(command=(FpCommand.IMAGE_CAPTURE_FREE if free else FpCommand.IMAGE_CAPTURE))

    def image_convert(self, buffer: tp.Union[int, FpBufferID]) -> FpResponseSet:
        """
        Converts the captured image and stores the result on the defined char buffer.

        :param Union[int, FpBufferID] buffer: Buffer ID.

        :return: Fingerprint set response.
        :rtype: FpResponseSet
        """
        if not FpBufferID.has_value(value=buffer):
            raise ValueError(f'Buffer value not supported: {buffer}')
        return self._command_set(command=FpCommand.IMAGE_CONVERT, packet=bytearray([FpBufferID(buffer)]))

    def image_download(self) -> FpResponseValue:
        """
        Downloads the fingerprint image from the image buffer.

        :return: Fingerprint value response.
        :rtype: FpResponseValue
        """
        # Get image bytes
        recv = self._command_get(command=FpCommand.IMAGE_DOWNLOAD, data_wait=True)

        # Generate image
        image = PilI.new(mode='L', size=(256, 288), color='white')
        if not recv.succ:
            return FpResponseValue(succ=recv.succ, code=recv.code, value=image)

        # Populate image
        pixel = image.load()
        width, height = image.size
        aux = width // 2
        for img_y in range(height):
            off = aux * img_y
            for img_x in range(aux):
                idx  = 2 * img_x
                byte = recv.data[off + img_x]
                pixel[idx, img_y]       = (0x0F & (byte >> 4)) << 4
                pixel[(idx + 1), img_y] = (0x0F & byte) << 4
        return FpResponseValue(succ=recv.succ, code=recv.code, value=image)

    def template_index(self) -> tp.Optional[FpResponseValue]:
        """
        Returns a list with the occupied indexes on the sensor database.

        :return: Fingerprint value response.
        :rtype: FpResponseValue
        """
        count = 0
        index = bytearray()
        pages = self.capacity // 256
        for page in range(pages + 1):
            recv = self._command_get(command=FpCommand.TEMPLATE_INDEX, packet=bytearray([page]))
            if not recv.succ:
                return FpResponseValue(succ=recv.succ, code=recv.code, value=bytearray())

            for byte in recv.pack:
                for bit in range(8):
                    index.append((byte & (1 << bit)) > 0)
                    count += 1
                    if count == self.capacity:
                        return FpResponseValue(succ=recv.succ, code=recv.code, value=index)
        return None

    def template_create(self) -> FpResponseSet:
        """
        Combines the contents of the char buffers into one template. The resulting template will be stored on both
        buffers.

        :return: Fingerprint set response.
        :rtype: FpResponseSet
        """
        return self._command_set(command=FpCommand.TEMPLATE_CREATE)

    def template_load(self, buffer: tp.Union[int, FpBufferID], index: int = 0) -> FpResponseValue:
        """
        Loads an existing template from the given database position into the specified char buffer.

        :param Union[int, FpBufferID] buffer: Buffer ID.
        :param int index: Position on the device database.

        :return: Fingerprint value response.
        :rtype: FpResponseValue
        """
        return self._template_manage(buffer=buffer, index=index, save=False)

    def template_save(self, buffer: tp.Union[int, FpBufferID], index: int = None) -> FpResponseValue:
        """
        Saves a template from the specified char buffer at the given database position.

        :param Union[int, FpBufferID] buffer: Buffer ID.
        :param int index: Position on the device database. If none it'll save it on the lowest free position.

        :return: Fingerprint value response.
        :rtype: FpResponseValue
        """
        return self._template_manage(buffer=buffer, index=index, save=True)

    def template_empty(self) -> FpResponseSet:
        """
        Delete all the templates from the device database.

        :return: Fingerprint set response.
        :rtype: FpResponseSet
        """
        return self._command_set(command=FpCommand.TEMPLATE_EMPTY)

    def template_delete(self, index: int = 0, count: int = 1) -> FpResponseSet:
        """
        Deletes a template from the device database. By default one.

        :param int index: Position on the device database.
        :param int count: Number of templates to be deleted.

        :return: Fingerprint set response.
        :rtype: FpResponseSet
        """
        if index < 0 or index >= self.capacity:
            raise ValueError(f'Index exceeds device capacity: 0 < index < {self.capacity}')
        if count < 0 or count > (self.capacity - index):
            raise ValueError(f'The selection exceeds bounds: {index + count} > {self.capacity}')
        pack = to_bytes(value=index, size=2) + to_bytes(value=count, size=2)
        return self._command_set(command=FpCommand.TEMPLATE_DELETE, packet=pack)

    def match_1_1(self) -> FpResponseMatch:
        """
        Compare the contents stored in the char buffers and returns the accuracy score.

        :return: Fingerprint match response.
        :rtype: FpResponseMatch
        """
        recv = self._command_get(command=FpCommand.TEMPLATE_MATCH)
        index = -1
        score = from_bytes(data=recv.pack[0:2])
        return FpResponseMatch(succ=recv.succ, code=recv.code, index=index, score=score)

    def match_1_n(self, buffer: tp.Union[int, FpBufferID], index: int = 0, count: int = None, fast: bool = False) -> FpResponseMatch:
        """
        Searches the device database for the template in char buffer.

        :param Union[int, FpBufferID] buffer: Buffer ID.
        :param int index: Position on the device database.
        :param int count: Number of templates to be compared.
        :param bool fast: True to perform a fast search, false otherwise.

        :return: Fingerprint match response.
        :rtype: FpResponseMatch
        """
        if count is None:
            count = (self.capacity - index)

        if index < 0 or index >= self.capacity:
            raise ValueError(f'Index exceeds device capacity: 0 < index < {self.capacity}')
        if count < 0 or count > (self.capacity - index):
            raise ValueError(f'The selection exceeds bounds: {index + count} > {self.capacity}')
        if not FpBufferID.has_value(value=buffer):
            raise ValueError(f'Buffer value not supported: {buffer}')

        cmd  = FpCommand.TEMPLATE_SEARCH_FAST if fast else FpCommand.TEMPLATE_SEARCH
        pack = bytearray([buffer]) + to_bytes(value=index, size=2) + to_bytes(value=count, size=2)
        recv = self._command_get(command=cmd, packet=pack)
        index = from_bytes(data=recv.pack[0:2]) if recv.succ else -1
        score = from_bytes(data=recv.pack[2:4])
        return FpResponseMatch(succ=recv.succ, code=recv.code, index=index, score=score)

    def buffer_download(self, buffer: tp.Union[int, FpBufferID]) -> FpResponseValue:
        """
        Downloads the char buffer data.

        :param Union[int, FpBufferID] buffer: Buffer ID.

        :return: Fingerprint value response.
        :rtype: FpResponseValue
        """
        if not FpBufferID.has_value(value=buffer):
            raise ValueError(f'{FpBufferID.__name__} value not supported: {buffer}')

        pack = bytearray([FpBufferID(buffer)])
        recv = self._command_get(command=FpCommand.TEMPLATE_DOWNLOAD, packet=pack, data_wait=True)
        return FpResponseValue(succ=recv.succ, code=recv.code, value=recv.data)

    def buffer_upload(self, buffer: tp.Union[int, FpBufferID], data: bytearray) -> FpResponseSet:
        """
        Uploads data to the char buffer. After transmission this function verifies the contents of the buffer to ensure
        the successful transmission.

        :param Union[int, FpBufferID] buffer: Buffer ID.
        :param bytearray data: Data to be uploaded to the buffer.

        :return: Fingerprint set response.
        :rtype: FpResponseSet
        """
        if not FpBufferID.has_value(value=buffer):
            raise ValueError(f'{FpBufferID.__name__} value not supported: {buffer}')
        if not data:
            raise ValueError('Data is empty')

        # Send
        recv = self._command_set(command=FpCommand.TEMPLATE_UPLOAD, data=data)
        if not recv.succ:
            return recv

        # Verify
        recv = self.buffer_download(buffer=buffer)
        succ = (recv.value == data)
        code = FpError.SUCCESS if succ else FpError.ERROR_TEMPLATE_UPLOAD
        return FpResponseSet(succ=succ, code=code)

    def notepad_get(self, page: int) -> FpResponseValue:
        """
        Get the selected notepad page contents.

        :param int page: Page number.

        :return: Fingerprint value response.
        :rtype: FpResponseValue
        """
        if page < 0 or page >= NOTEPAD_COUNT:
            raise ValueError(f'Notepad page out of range: {0} <= {page} < {NOTEPAD_COUNT}')

        recv = self._command_get(command=FpCommand.NOTEPAD_GET, packet=bytearray([page]))
        if len(recv.pack) != NOTEPAD_SIZE:
            raise BufferError(f'Notepad size is not the expected: {len(recv.pack)} instead of {NOTEPAD_SIZE}')
        return FpResponseValue(succ=recv.succ, code=recv.code, value=recv.pack)

    def notepad_set(self, page: int, data: bytearray) -> FpResponseSet:
        """
        Set the selected notepad page contents.

        :param int page:        Page number.
        :param bytearray data:  Data to be written on the page.

        :return: Fingerprint set response.
        :rtype: FpResponseSet
        """
        if page < 0 or page >= NOTEPAD_COUNT:
            raise ValueError(f'Notepad page out of range: {0} <= {page} < {NOTEPAD_COUNT}')
        if len(data) > NOTEPAD_SIZE:
            embu.SDK_LOG.info(f'Cropping data to match the notepad page size: {len(data)} cropped to {NOTEPAD_SIZE}')
            data = data[:NOTEPAD_SIZE]

        pack = bytearray([page]) + data
        return self._command_set(command=FpCommand.NOTEPAD_SET, packet=pack)

    def notepad_clear(self, page: int) -> FpResponseSet:
        """
        Clear the contents of the selected notepad page.

        :param int page: Page number.

        :return: Fingerprint set response.
        :rtype: FpResponseSet
        """
        return self.notepad_set(page=page, data=bytearray(NOTEPAD_SIZE * [0x00]))

    def random_get(self) -> FpResponseValue:
        """
        Generates a random 32-bit decimal number.

        :return: Fingerprint value response.
        :rtype: FpResponseValue
        """
        recv = self._command_get(command=FpCommand.GENERATE_RANDOM)
        return FpResponseValue(succ=recv.succ, code=recv.code, value=from_bytes(data=recv.pack[0:4]))

    def _detector_process(self) -> None:
        """
        Pulls periodically the state of the TOUT signal connected to CTS. If the finger is detected then an event is
        emitted.
        """
        # Do this periodically
        while self._df_is_active:
            # Only execute core if device IS connected...
            if self.stream.device.is_open:
                state = self.stream.device.serial.cts
                if state != self._df_state:
                    self._df_state = state
                    if self._df_state:
                        embu.SDK_LOG.info('Finger pressed sensor!')
                        embu.SDK_TP.enqueue(task=embu.SimpleThreadTask(
                            name=f'{self.__class__.__name__}.on_finger_pressed',
                            task=self.on_finger_pressed.emit
                            ))
                    else:
                        embu.SDK_LOG.info('Finger released sensor!')
                        embu.SDK_TP.enqueue(task=embu.SimpleThreadTask(
                            name=f'{self.__class__.__name__}.on_finger_released',
                            task=self.on_finger_released.emit
                            ))
            time.sleep(self._df_period)

        # Inform finished
        self._df_finished = True

    def _command_get(self,
                     command: FpCommand, packet: bytearray = bytearray(),
                     data_wait: bool = False
                     ) -> FpResponseGet:
        """
        Use this function when need to get parameters / data from to the device.

        :param FpCommand command:   Command ID.
        :param bytearray packet:    Command packet.
        :param bool data_wait:      True if waiting for data, False otherwise.

        :return: Fingerprint get response.
        :rtype: FpResponseGet
        """
        tim = embu.Timer()
        data_ok = False
        data_buff = bytearray()

        def wait_ack_logic(item: FpPacket) -> bool:
            """
            Wait for ACK.
            """
            is_ack = (item.pid == FpPID.ACK)
            return is_ack

        def wait_data_logic(item: FpPacket) -> None:
            """
            Wait for data to be received.
            """
            nonlocal data_buff, data_ok, tim
            is_data = (item.pid == FpPID.DATA)
            is_end = (item.pid == FpPID.END_OF_DATA)
            if is_data or is_end:
                tim.start()
                data_buff.extend(item.packet)
            if is_end:
                data_ok = True

        # Prepare data reception
        if data_wait:
            self.on_receive += wait_data_logic

        # Transmit packet and wait response
        send = FpPacket(address=self._addr, pid=FpPID.COMMAND, packet=bytearray([command]) + packet)
        recv = self.transmit(send=send, logic=wait_ack_logic)

        # Check response type, command and possible errors
        if not isinstance(recv, FpPacket):
            raise self.Error(message='Unable to get the response packet', code=FpError.ERROR_PACKET_RECEPTION)
        if recv.pid != FpPID.ACK:
            raise self.Error(message='The received packet is not an ACK!', code=FpError.ERROR_PACKET_FAULTY)
        pack = recv.packet[1:]
        code = FpError(recv.packet[0])
        self._code_check(code=code)

        # Wait for data if required
        if data_wait:
            tim.start()
            while not data_ok and (tim.elapsed() < self._timeout):
                time.sleep(0.01)
            self.on_receive -= wait_data_logic
            if not data_ok:
                raise self.Error('Timeout while waiting for data.', code=FpError.ERROR_TIMEOUT)

        # Check and return
        succ = code in [FpError.SUCCESS, FpError.HANDSHAKE_SUCCESS]
        return FpResponseGet(succ=succ, code=code, pack=pack, data=data_buff)

    def _command_set(self,
                     command: FpCommand, packet: bytearray = bytearray(),
                     data: bytearray = bytearray()
                     ) -> FpResponseSet:
        """
        Use this function when need to set parameters / data to the device.

        :param FpCommand command:   Command ID.
        :param bytearray packet:    Command packet.
        :param bytearray data:      If not empty this data will be sent after successful command.

        :return: Fingerprint set response.
        :rtype: FpResponseSet
        """
        # Send command
        recv = self._command_get(command=command, packet=packet)

        # Send data, if required
        if data and recv.succ:
            data_size = len(data)
            pack_size = self.packet_size.to_int()
            pack_num  = (data_size // pack_size) + int((data_size % pack_size) > 0)

            end  = 0
            send = FpPacket(address=self._addr, pid=FpPID.DATA)
            for idx in range(pack_num - 1):
                start = idx * pack_size
                end   = start + pack_size
                send.packet = data[start:end]
                self.transmit(send=send)

            send.pid    = FpPID.END_OF_DATA
            send.packet = data[end:]
            self.transmit(send=send)

        return FpResponseSet(succ=recv.succ, code=recv.code)

    def _template_manage(self, buffer: tp.Union[int, FpBufferID], index: int = None, save: bool = True) -> FpResponseValue:
        """
        Save/load a template to/from the device database.

        :param Union[int, FpBufferID] buffer: Buffer ID.
        :param int index: Position on the device database.
        :param bool save: If true, saves the template in the char buffer to the device database.

        :return: Fingerprint value response.
        :rtype: FpResponseValue
        """
        if index is None:
            if self.count >= self.capacity:
                raise self.Error(message='No space available on database', code=FpError.ERROR_DATABASE_FULL)
            index = self.template_index().value.find(0x00)

        if index < 0 or index >= self.capacity:
            raise ValueError(f'Index exceeds device capacity: 0 < index < {self.capacity}')
        if not FpBufferID.has_value(value=buffer):
            raise ValueError(f'Buffer value not supported: {buffer}')

        cmd  = FpCommand.TEMPLATE_SAVE if save else FpCommand.TEMPLATE_LOAD
        pack = bytearray([FpBufferID(buffer)]) + to_bytes(value=index, size=2)
        recv = self._command_set(command=cmd, packet=pack)
        return FpResponseValue(succ=recv.succ, code=recv.code, value=index)

    def _value_set(self, command: FpCommand, value: int) -> FpResponseSet:
        """
        Set the selected command with the given value.

        :param FpCommand command: Command ID.
        :param int value: Value to set.

        :return: Fingerprint set response.
        :rtype: FpResponseSet
        """
        value = to_bytes(value=self._auth_check(value=value), size=4)
        return self._command_set(command=command, packet=value)

    def _parameter_set(self, param: FpParameterID, value: tp.Union[int, FpBaudrate, FpPacketSize, FpSecurity]) -> FpResponseSet:
        """
        Set the selected parameter with the given value.

        :param FpParameterID param: Parameter ID.
        :param Union[int, FpBaudrate, FpPacketSize, FpSecurity] value: Parameter setting.

        :return: Fingerprint set response.
        :rtype: FpResponseSet
        """
        # Get type
        _type = param.get_type()
        try:
            value = _type.from_int(value=value)
        except ValueError as error:
            raise ValueError(f'{_type.__name__} value not supported: {value}') from error

        # Perform operation
        value = _type(value)
        recv = self._command_set(command=FpCommand.PARAMETERS_SET, packet=bytearray([param, value]))
        if recv.succ and param == FpParameterID.BAUDRATE:
            # Handle special case for baudrate...
            embu.SDK_LOG.info(f'Updating serial baudrate to {str(value)}...')
            self.stream.pause()
            self.stream.device.serial.baudrate = value.to_int()
            self.stream.resume()
        return recv

    @staticmethod
    def _code_check(code: FpError) -> None:
        """
        Check if the given response is valid.

        :param FpError code: code to check.

        :raise FpSDK.Error: Raise if the code is an error.
        """
        if code == FpError.ERROR_PACKET_TRANSMISSION:
            raise FpSDK.Error(message='Communication error!', code=code)
        if code == FpError.ERROR_ADDRESS:
            raise FpSDK.Error(message='Sensor address is wrong!', code=code)
        if code == FpError.ERROR_PASSWORD:
            raise FpSDK.Error(message='Sensor password is wrong!', code=code)
        if code == FpError.ERROR_PASSWORD_VERIFY:
            raise FpSDK.Error(message='Password verification required!', code=code)

    @staticmethod
    def _auth_check(value: int) -> int:
        """
        Check and returns if the given addr/pass value is in a valid range.

        :param int value: Value to be checked.

        :return: Value if valid.
        :rtype: int

        :raise ValueError: Raise if value is not in valid range.
        """
        if value < 0x00000000 or value > 0xFFFFFFFF:
            raise ValueError(f'Value out of range (0x00000000 < 0x{value:08X} < 0xFFFFFFFF)!')
        return value
