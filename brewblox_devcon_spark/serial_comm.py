"""
Implements a protocol and a conduit for async serial communication.
"""

import asyncio
import logging
import re
from typing import Tuple, Callable
# from typing import Tuple, Iterable, Generator, Callable
from functools import partial

import serial
from serial.aio import SerialTransport
# from serial.tools import list_ports

LOGGER = logging.getLogger(__name__)

DeviceType_ = Tuple[str, str, str]
MessageCallback_ = Callable[['SparkConduit', str], None]


PARTICLE_DEVICES = {
    (r'Spark Core.*Arduino.*', r'USB VID\:PID=1D50\:607D.*'): 'Spark Core',
    (r'.*Photon.*', r'USB VID\:PID=2d04\:c006.*'): 'Particle Photon',
    (r'.*P1.*', r'USB VID\:PID=2d04\:c008.*'): 'Particle P1',
    (r'.*Electron.*', r'USB VID\:PID=2d04\:c00a.*'): 'Particle Electron'
}

KNOWN_DEVICES = dict((k, v) for d in [PARTICLE_DEVICES] for k, v in d.items())
DEFAULT_BAUD_RATE = 57600
AUTO_PORT = 'auto'


async def _default_on_message(conduit: 'SparkConduit', message: str):
    LOGGER.info(f'Unhandled message: conduit={conduit}, message={message}')


class SparkConduit():

    def __init__(self,
                 on_event: MessageCallback_=None,
                 on_data: MessageCallback_=None):
        # Communication
        self._port = None
        self._protocol = None
        self._serial = None

        # Callback handling
        self.on_event = on_event
        self.on_data = on_data

    @property
    def on_event(self) -> MessageCallback_:
        return self._on_event

    @on_event.setter
    def on_event(self, f: MessageCallback_):
        self._on_event = f if f else _default_on_message

    @property
    def on_data(self) -> MessageCallback_:
        return self._on_data

    @on_data.setter
    def on_data(self, f: MessageCallback_):
        self._on_data = f if f else _default_on_message

    @property
    def is_bound(self):
        return self._serial and self._serial.is_open

    def bind(self, port: str=AUTO_PORT, loop: asyncio.BaseEventLoop=None):
        loop = loop or asyncio.get_event_loop()

        # TODO(Bob): use detect port
        self._port = port
        self._protocol = SparkProtocol(
            on_event=partial(self._do_callback, loop, 'on_event'),
            on_data=partial(self._do_callback, loop, 'on_data'))
        self._serial = serial.serial_for_url(self._port, baudrate=DEFAULT_BAUD_RATE)
        self._transport = SerialTransport(loop, self._protocol, self._serial)

        return self._transport is not None

    async def write(self, data):
        assert self._serial, 'Serial unbound or not available'
        self._serial.write(data)

    def _do_callback(self, loop, cb_attr, message):
        # Retrieve the callback function every time to allow changing it
        func = getattr(self, cb_attr)
        # ensure_future does not raise exceptions
        asyncio.ensure_future(func(self, message), loop=loop)


class SparkProtocol(asyncio.Protocol):
    def __init__(self,
                 on_event: Callable[[str], None],
                 on_data: Callable[[str], None]):
        super().__init__()
        self._on_event = on_event
        self._on_data = on_data
        self._buffer = ''

    def connection_made(self, transport):
        transport.serial.rts = False
        LOGGER.debug(f'Serial connection made: {transport}')

    def data_received(self, data):
        self._buffer += data.decode()

        # Annotations use < and > as start/end characters
        # Most annotations can be discarded, except for event messages
        # Event messages are annotations that start with !
        for event in self._coerce_message_from_buffer(start='<', end='>', filter_expr='!([\s\S]*)'):
            self._on_event(event)

        # Once annotations are filtered, all that remains is data
        # Data is newline-separated
        for data in self._coerce_message_from_buffer(start='^', end='\n'):
            self._on_data(data)

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


# def all_serial_devices() -> Iterable[DeviceType_]:
#     return tuple(list_ports.comports())


# def all_serial_ports() -> Generator[str, None, None]:
#     for port, desc, hwid in all_serial_devices():
#         yield port


# def recognized_serial_ports(devices: Iterable[DeviceType_]) -> Generator[str, None, None]:
#     devices = devices if devices is not None else all_serial_devices()
#     for device in devices:
#         if is_recognized_device(device):
#             yield device[0]


# def is_recognized_device(device: DeviceType_):
#     port, desc, hwid = device
#     for (device_name, device_desc) in KNOWN_DEVICES.keys():
#         # used to match on name and desc, but under linux only desc is
#         # returned, compared
#         if re.match(device_desc, desc):
#             return True
#     return False


# def detect_port(port: str) -> str:
#     if port == AUTO_PORT:
#         devices = all_serial_devices()
#         ports = tuple(recognized_serial_ports(devices))
#         if not ports:
#             raise ValueError(
#                 f'Could not find recognized device. Known={[{v for v in d} for d in devices]}')
#         return ports[0]

#     return port
