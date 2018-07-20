"""
Implements a protocol and a conduit for async serial communication.
"""

import asyncio
import re
from collections import namedtuple
from concurrent.futures import CancelledError
from contextlib import suppress
from functools import partial
from typing import Any, Awaitable, Callable, Generator, Iterable, List, Tuple

import serial
from aiohttp import web
from brewblox_service import brewblox_logger, features, scheduler
from serial.tools import list_ports
from serial_asyncio import SerialTransport

LOGGER = brewblox_logger(__name__)
DEFAULT_BAUD_RATE = 57600
RETRY_INTERVAL_S = 1

PortType_ = Any
MessageCallback_ = Callable[['SparkConduit', str], Awaitable]
ProtocolFactory_ = Callable[[], asyncio.Protocol]
ConnectionResult_ = Tuple[Any, asyncio.Transport, asyncio.Protocol]

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


def setup(app: web.Application):
    features.add(app, SparkConduit(app))


def get_conduit(app: web.Application) -> 'SparkConduit':
    return features.get(app, SparkConduit)


async def connect_serial(app: web.Application,
                         factory: ProtocolFactory_
                         ) -> Awaitable[ConnectionResult_]:
    config = app['config']
    port = config['device_port']
    id = config['device_id']

    address = detect_device(port, id)
    protocol = factory()
    ser = serial.serial_for_url(address, baudrate=DEFAULT_BAUD_RATE)
    transport = SerialTransport(app.loop, protocol, ser)
    transport.serial.rts = False
    return address, transport, protocol


async def connect_tcp(app: web.Application,
                      factory: ProtocolFactory_
                      ) -> Awaitable[ConnectionResult_]:
    address = app['config']['device_url']
    port = app['config']['device_url_port']
    transport, protocol = await app.loop.create_connection(
        factory,
        address,
        port
    )
    return address, transport, protocol


class SparkConduit(features.ServiceFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)

        self._connection_task: asyncio.Task = None

        self._address: Any = None
        self._transport: asyncio.Transport = None
        self._protocol: 'SparkProtocol' = None

        self._event_callbacks = set()
        self._data_callbacks = set()

    def __str__(self):
        return f'<{type(self).__name__} for {self._address}>'

    @property
    def connected(self) -> bool:
        return bool(self._transport and not self._transport.is_closing())

    def add_event_callback(self, cb: MessageCallback_):
        cb and self._event_callbacks.add(cb)

    def remove_event_callback(self, cb: MessageCallback_):
        with suppress(KeyError):
            self._event_callbacks.remove(cb)

    def add_data_callback(self, cb: MessageCallback_):
        cb and self._data_callbacks.add(cb)

    def remove_data_callback(self, cb: MessageCallback_):
        with suppress(KeyError):
            self._data_callbacks.remove(cb)

    async def startup(self, app: web.Application):
        await self.shutdown()

        def factory():
            return SparkProtocol(
                on_event=partial(self._do_callbacks, self._event_callbacks),
                on_data=partial(self._do_callbacks, self._data_callbacks)
            )

        if app['config']['device_url']:
            connect_func = partial(connect_tcp, self.app, factory)
        else:
            connect_func = partial(connect_serial, self.app, factory)

        self._connection_task = await scheduler.create_task(
            self.app,
            self._maintain_connection(connect_func)
        )

    async def shutdown(self, *_):
        await scheduler.cancel_task(self.app, self._connection_task)
        self._connection_task = None

    async def write(self, data: str):
        return await self.write_encoded(data.encode())

    async def write_encoded(self, data: bytes):
        if not self.connected:
            raise ConnectionError(f'{self} not connected')
        LOGGER.debug(f'{self} writing: {data}')
        self._transport.write(data + b'\n')

    def _do_callbacks(self, callbacks: List[MessageCallback_], message: str):
        async def call_cb(cb: MessageCallback_, message: str):
            try:
                await cb(self, message)
            except Exception as ex:
                LOGGER.warn(f'Unhandled exception in {cb}, message={message}, ex={ex}')

        for cb in callbacks or [_default_on_message]:
            self.app.loop.create_task(call_cb(cb, message))

    async def _maintain_connection(self, connect_func: Callable[[], Awaitable[ConnectionResult_]]):
        while True:
            try:
                self._address, self._transport, self._protocol = await connect_func()

                await self._protocol.connected
                LOGGER.info(f'Connected {self}')

                await self._protocol.disconnected
                LOGGER.info(f'Disconnected {self}')

            except CancelledError:
                with suppress(Exception):
                    await self._transport.close()
                break

            except Exception as ex:
                LOGGER.debug(f'Connection failed: {ex}')
                await asyncio.sleep(RETRY_INTERVAL_S)

            finally:
                # Keep last known address
                self._transport = None
                self._protocol = None


class SparkProtocol(asyncio.Protocol):
    def __init__(self,
                 on_event: Callable[[str], None],
                 on_data: Callable[[str], None]
                 ):
        super().__init__()
        self._connection_made_event = asyncio.Event()
        self._connection_lost_event = asyncio.Event()
        self._on_event = on_event
        self._on_data = on_data
        self._buffer = ''

    @property
    def connected(self) -> Awaitable:
        return self._connection_made_event.wait()

    @property
    def disconnected(self) -> Awaitable:
        return self._connection_lost_event.wait()

    def connection_made(self, transport):
        self._connection_made_event.set()

    def connection_lost(self, exc):
        self._connection_lost_event.set()
        if exc:
            LOGGER.warning(f'Protocol connection error: {exc}')

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
