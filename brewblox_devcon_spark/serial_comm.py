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
    def __init__(self, loop):
        super().__init__()
        self._loop = loop
        self._data_messages = asyncio.Queue()
        self._event_messages = asyncio.Queue()
        self._buffer = ''

    @property
    def events(self):
        return self._event_messages

    @property
    def data(self):
        return self._data_messages

    def connection_made(self, transport):
        transport.serial.rts = False
        LOGGER.debug(f'Serial connection made: {transport}')

    def data_received(self, data):
        self._buffer += data.decode()

        # Annotations use < and > as start/end characters
        # Most annotations can be discarded, except for event messages
        # Event messages are annotations that start with !
        for event in self._coerce_message_from_buffer(start='<', end='>', filter_expr='!([\s\S]*)'):
            self._event_messages.put_nowait(event)

        # Once annotations are filtered, all that remains is data
        # Data is newline-separated
        for data in self._coerce_message_from_buffer(start='^', end='\n'):
            self._data_messages.put_nowait(data)

    def connection_lost(self, exc):
        LOGGER.warn(f'port closed: {exc}')

    def _coerce_message_from_buffer(self, start: str, end: str, filter_expr: str=None):
        """ Filters separate messages from the buffer.

        It makes some assumptions about messages:
        * They have a fixed start/end special character
        * Start/end characters should not be included in yielded messages
        * Messages do not include start/end characters of other message types
        * Messages can be nested
        * If a filter expression is specified, each capture should be a separate message

        Returned messages are ordered on the position of their end character.
        Given the buffer: (< and > are start/end characters)

            '<messageA <messageB> <messageC> > data <messageD>'

        Yielded messages will be:

            [
                'messageB',
                'messageC',
                'messageA   ',
                'messageD'
            ]

        Afterwards, the buffer will contain ' data '
        """
        messages = []

        def extract_message(matchobj) -> str:
            msg = matchobj.group('message')

            if filter_expr is None:
                messages.append(msg)
            else:
                [messages.append(m) for m in re.findall(filter_expr, msg)]

            return ''

        while re.search(f'.*{start}.*{end}', self._buffer):
            self._buffer = re.sub(
                pattern=f'{start}(?P<message>[^{start}]*?){end}',
                repl=extract_message,
                string=self._buffer,
                count=1)

        yield from messages


class SerialConduit():

    def __init__(self, port: str=AUTO_PORT, loop: asyncio.BaseEventLoop=None):
        self._loop = loop or asyncio.get_event_loop()
        self.port = detect_port(port)
        self.transport = None
        self.serial = serial.serial_for_url(port, baudrate=DEFAULT_BAUD_RATE)
        self.protocol = SerialProtocol(self._loop)

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


def all_serial_ports() -> Generator[str, None, None]:
    for (port, name, desc) in all_serial_devices():
        yield port


def recognized_serial_ports(devices: Iterable[DeviceType_]) -> Generator[str, None, None]:
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
