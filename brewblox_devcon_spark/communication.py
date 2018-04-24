"""
Implements a protocol and a conduit for async serial communication.
"""

import asyncio
import re
from collections import namedtuple
from functools import partial
from typing import Callable, Generator, Iterable, Any

import serial
from brewblox_devcon_spark import brewblox_logger
from serial.aio import SerialTransport
from serial.tools import list_ports

LOGGER = LOGGER = brewblox_logger(__name__)
DEFAULT_BAUD_RATE = 57600

PortType_ = Any
MessageCallback_ = Callable[['SparkConduit', str], None]

DeviceMatch = namedtuple('DeviceMatch', ['id', 'desc', 'hwid'])

KNOWN_DEVICES = {
    DeviceMatch(
        id='Spark Core',
        desc=r'Spark Core.*Arduino.*',
        hwid=r'USB VID\:PID=1D50\:607D.*'),
    DeviceMatch(
        id='Particle Photon',
        desc=r'.*Photon.*',
        hwid=r'USB VID\:PID=2d04\:c006.*'),
    DeviceMatch(
        id='Particle P1',
        desc=r'.*P1.*',
        hwid=r'USB VID\:PID=2B04\:C008.*'),
}


async def _default_on_message(conduit: 'SparkConduit', message: str):
    LOGGER.info(f'Unhandled message: conduit={conduit}, message={message}')


class SparkConduit():

    def __init__(self,
                 on_event: MessageCallback_=None,
                 on_data: MessageCallback_=None):
        # Communication
        self._device = None
        self._protocol = None
        self._serial = None
        self._transport = None

        # Callback handling
        self.on_event = on_event
        self.on_data = on_data

        # Asyncio
        self._loop = None

    def __str__(self):
        return f'<{type(self).__name__} for {self._device}>'

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

    def bind(self, device: str=None, serial_number: str=None, loop: asyncio.BaseEventLoop=None):
        self.close()
        self._loop = loop or asyncio.get_event_loop()

        self._device = detect_device(device, serial_number)
        self._protocol = SparkProtocol(
            on_event=partial(self._do_callback, 'on_event'),
            on_data=partial(self._do_callback, 'on_data'))
        self._serial = serial.serial_for_url(self._device, baudrate=DEFAULT_BAUD_RATE)
        self._transport = SerialTransport(self._loop, self._protocol, self._serial)

        LOGGER.info(f'Conduit bound to {self._transport}')
        return self._transport is not None

    def close(self):
        if self._transport:
            self._transport.close()

        self._loop = None
        self._device = None
        self._protocol = None
        self._serial = None
        self._transport = None

    async def write(self, data: str):
        return await self.write_encoded(data.encode())

    async def write_encoded(self, data: bytes):
        LOGGER.debug(f'{self} writing: {data}')
        data += b'\n'
        assert self._serial, 'Serial unbound or not available'
        return self._serial.write(data)

    def _do_callback(self, cb_attr: str, message: str):
        LOGGER.debug(f'{self} {cb_attr}({message})')

        def check_result(fut):
            try:
                fut.result()
            except Exception as ex:
                LOGGER.warn(f'Unhandled exception in callback {self}, message={message}, ex={ex}')

        # Retrieve the callback function every time to allow changing it
        func = getattr(self, cb_attr)
        # Schedule the callback for execution
        task = asyncio.ensure_future(func(self, message), loop=self._loop)
        task.add_done_callback(check_result)


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
        for event in self._coerce_message_from_buffer(start='<', end='>', filter_expr='^!([\s\S]*)'):
            self._on_event(event)

        # Once annotations are filtered, all that remains is data
        # Data is newline-separated
        for data in self._coerce_message_from_buffer(start='^', end='\n'):
            self._on_data(data)

    def connection_lost(self, exc):
        LOGGER.warn(f'Protocol connection lost, error: {exc}')

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
            msg = matchobj.group('message').rstrip()

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


def all_ports() -> Iterable[PortType_]:
    return tuple(list_ports.comports())


def recognized_ports(
    allowed: Iterable[DeviceMatch]=KNOWN_DEVICES,
    serial_number: str=None
) -> Generator[PortType_, None, None]:

    # Construct a regex OR'ing all allowed hardware ID matches
    # Example result: (?:HWID_REGEX_ONE|HWID_REGEX_TWO)
    matcher = f'(?:{"|".join([dev.hwid for dev in allowed])})'

    for port in list_ports.grep(matcher):
        if serial_number is None or serial_number == port.serial_number:
            yield port


def detect_device(device: str=None, serial_number: str=None) -> str:
    if device is None:
        try:
            port = next(recognized_ports(serial_number=serial_number))
            device = port.device
            LOGGER.info(f'Automatically detected {[v for v in port]}')
        except StopIteration:
            raise ValueError(
                f'Could not find recognized device. Known={[{v for v in p} for p in all_ports()]}')

    return device
