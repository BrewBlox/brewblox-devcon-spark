"""
Implements a protocol and a conduit for async serial communication.
"""

import asyncio
import logging
import re
from typing import Tuple, Iterable, Generator, Callable

import serial
from serial.aio import SerialTransport
from serial.tools import list_ports
from overrides import overrides

LOGGER = logging.getLogger(__name__)

DeviceType_ = Tuple[str, str, str]
DataCallback_ = Callable[[str], None]
DebugCallback_ = Callable[[str], None]


PARTICLE_DEVICES = {
    (r'Spark Core.*Arduino.*', r'USB VID\:PID=1D50\:607D.*'): 'Spark Core',
    (r'.*Photon.*', r'USB VID\:PID=2d04\:c006.*'): 'Particle Photon',
    (r'.*P1.*', r'USB VID\:PID=2d04\:c008.*'): 'Particle P1',
    (r'.*Electron.*', r'USB VID\:PID=2d04\:c00a.*'): 'Particle Electron'
}

KNOWN_DEVICES = dict((k, v) for d in [PARTICLE_DEVICES] for k, v in d.items())
DEFAULT_BAUD_RATE = 57600
AUTO_PORT = 'auto'


class SerialProtocol(asyncio.Protocol):
    def __init__(self):
        super().__init__()
        self._msg_queue = asyncio.Queue()
        self._buffer = ''
        self._transport = None

    def __str__(self):
        return f'<{type(self).__name__}>'

    @overrides
    def connection_made(self, transport):
        self._transport = transport
        self._transport.serial.rts = False
        LOGGER.debug(f'Serial connection made: {transport}')

    @overrides
    def data_received(self, data):
        self._buffer += data.decode()

        # '<add>0A<id>00<OneWir<!connected:sensor>eTempSensor>01<address>28C80E9A0300009C\n'

        # for event in self._parse(start='<', end='>'):
        #     pass

        # for data in self._parse(start='^', end='\n'):
        #     pass

        # for event in self._parse_events_from_buffer():
        #     '<add>'
        #     '<id>'
        #     '<!connected:sensor>'  # yielded
        #     '<OnewireTempSensor>'
        #     '<address>'

        # leftovers 0a000128C80E9A0300009C\n

        # for data in self._parse_data_from_buffer():
        #     '0a000128C80E9A0300009C'  # yield

        # for anno in self._coerce_annotations_from_buffer():
        #     if anno[0] in '![':
        #         self.on_annotations(anno)

        # for data in self._coerce_data_from_buffer():
        #     self.on_data(data)

        # coerce debug from buffer
        # coerce data from buffer

        # for line in self._coerce_message_from_buffer():
        #     LOGGER.debug(f'new full line: {line}')
        #     line = line.replace(' ', '')
        #     self._msg_queue.put_nowait(line.encode())  # FIXME: Make sure it's right

    @overrides
    def connection_lost(self, exc):
        LOGGER.debug(f'port closed: {exc}')
        asyncio.get_event_loop().stop()

    # async def watch_messages(self):
    #     LOGGER.debug('watching message queue...')
    #     while True:
    #         yield await self._msg_queue.get()

    def _coerce_message_from_buffer(self, start: str, end: str, filter_expr: str=None):
        messages = []

        def remove_message(matchobj) -> str:
            msg = matchobj.group()
            LOGGER.info(msg)
            # discard all messages that do not match the (optional) filter expression
            if filter_expr is None or re.match(filter_expr, msg) is not None:
                messages.append(msg)
            return ''

        while end in self._buffer:
            self._buffer = re.sub(
                pattern=f'{start}.*?{end}',
                repl=remove_message,
                string=self._buffer,
                count=1)

        yield from messages

    def _orig_coerce_message_from_buffer(self):
        """
        Try to make a message out of the buffer and find log messages intertwined
        into the buffer.
        """
        log_messages = []
        while '\n' in self._buffer:
            # stripped_buffer, log_messages = self._filter_out_log_messages(self.buffer)
            if len(log_messages) > 0:
                yield from log_messages
                # self._buffer = stripped_buffer
                continue

            lines = self._buffer.partition('\n')  # returns 3-tuple with line, separator, rest
            if not lines[1]:
                # '\n' not found, first element is incomplete line
                self._buffer = lines[0]
            else:
                # complete line received, [0] is complete line [1] is separator [2] is the rest
                self._buffer = lines[2]
                yield lines[0].rstrip('\r').rstrip('\n')


# Keep??
class SerialConduit():

    def __init__(self, port: str=AUTO_PORT, loop: asyncio.BaseEventLoop=None):
        self._loop = loop or asyncio.get_event_loop()
        self.port = detect_port(port)
        self.transport = None
        self.serial = serial.serial_for_url(port, baudrate=DEFAULT_BAUD_RATE)
        self.protocol = SerialProtocol()

    def bind(self):
        self.transport = SerialTransport(self._loop, self.protocol, self.serial)
        return self.transport is not None

    async def write(self, data):
        self.serial.write(data)

    async def watch_messages(self):
        yield await self.protocol.watch_messages()

    @property
    def is_bound(self):
        return self.serial.is_open


def all_serial_devices() -> Iterable[DeviceType_]:
    return tuple(list_ports.comports())


def all_serial_ports() -> Generator[str]:
    for (port, name, desc) in all_serial_devices():
        yield port


def recognized_serial_ports(devices: Iterable[DeviceType_]) -> Generator[str]:
    devices = devices if devices is not None else all_serial_devices()
    for device in devices:
        if is_recognized_device(device):
            yield device[0]


def is_recognized_device(device: DeviceType_):
    port, name, desc = device
    for (device_name, device_desc) in KNOWN_DEVICES.keys():
        # used to match on name and desc, but under linux only desc is
        # returned, compared
        if re.match(device_desc, desc):
            return True
    return False


def detect_port(port: str) -> str:
    if port == AUTO_PORT:
        devices = all_serial_devices()
        ports = tuple(recognized_serial_ports(devices))
        if not ports:
            raise ValueError(f'Could not find recognized device. {repr(devices)}')
        return ports[0]

    return port
