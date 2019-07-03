"""
Implements a protocol and a conduit for async serial communication.
"""

import asyncio
import re
import warnings
from asyncio import TimeoutError
from collections import namedtuple
from concurrent.futures import CancelledError
from contextlib import suppress
from functools import partial
from typing import Any, Awaitable, Callable, Iterable, Iterator, List, Tuple

import serial
from aiohttp import web
from brewblox_service import brewblox_logger, features, scheduler
from serial.tools import list_ports
from serial_asyncio import SerialTransport

from brewblox_devcon_spark import exceptions, http_client, status

LOGGER = brewblox_logger(__name__)
DNS_DISCOVER_TIMEOUT_S = 20
DEFAULT_BAUD_RATE = 57600
RETRY_INTERVAL_S = 2
DISCOVER_INTERVAL_S = 10
DISCOVERY_RETRY_COUNT = 5

PortType_ = Any
MessageCallback_ = Callable[['SparkConduit', str], Awaitable]
ProtocolFactory_ = Callable[[], asyncio.Protocol]
ConnectionResult_ = Tuple[Any, asyncio.Transport, asyncio.Protocol]

DeviceMatch = namedtuple('DeviceMatch', ['id', 'desc', 'hwid'])

KNOWN_DEVICES = {
    DeviceMatch(
        id='Particle Photon',
        desc=r'.*Photon.*',
        hwid=r'USB VID\:PID=2B04\:C006.*'),
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


async def create_connection(*args, **kwargs):  # pragma: no cover
    """asyncio.create_connection() wrapper, for easier testing"""
    return await asyncio.get_event_loop().create_connection(*args, **kwargs)


def exit_discovery():  # pragma: no cover
    """SystemExit wrapper, to allow mocking"""
    LOGGER.error('Device discovery failed. Exiting now.')
    raise SystemExit(1)


async def connect_serial(app: web.Application,
                         factory: ProtocolFactory_
                         ) -> Awaitable[ConnectionResult_]:
    config = app['config']
    port = config['device_serial']
    id = config['device_id']

    address = detect_device(port, id)
    protocol = factory()
    ser = serial.serial_for_url(address, baudrate=DEFAULT_BAUD_RATE)
    loop = asyncio.get_event_loop()
    transport = SerialTransport(loop, protocol, ser)
    transport.serial.rts = False
    transport.set_write_buffer_limits(high=255)  # receiver RX buffer is 256, so limit send buffer to 255
    return address, transport, protocol


async def connect_tcp(app: web.Application,
                      factory: ProtocolFactory_
                      ) -> Awaitable[ConnectionResult_]:
    host = app['config']['device_host']
    port = app['config']['device_port']
    transport, protocol = await create_connection(factory, host, port)
    return f'{host}:{port}', transport, protocol


async def discover_serial(app: web.Application, factory: ProtocolFactory_) -> Awaitable[ConnectionResult_]:
    try:
        return await connect_serial(app, factory)
    except exceptions.ConnectionImpossible:
        return None


async def discover_tcp(app: web.Application, factory: ProtocolFactory_) -> Awaitable[ConnectionResult_]:
    config = app['config']
    id = config['device_id']
    mdns_host = config['mdns_host']
    mdns_port = config['mdns_port']
    try:
        session = http_client.get_client(app).session
        retv = await asyncio.wait_for(
            session.post(f'http://{mdns_host}:{mdns_port}/mdns/discover', json={'id': id}),
            DNS_DISCOVER_TIMEOUT_S
        )
        resp = await retv.json()
        host, port = resp['host'], resp['port']
        transport, protocol = await create_connection(factory, host, port)
        return f'{host}:{port}', transport, protocol

    except TimeoutError:  # pragma: no cover
        return None


async def connect_discovered(app: web.Application,
                             factory: ProtocolFactory_
                             ) -> Awaitable[ConnectionResult_]:
    discovery_type = app['config']['discovery']
    LOGGER.info(f'Starting device discovery, type={discovery_type}')

    for i in range(DISCOVERY_RETRY_COUNT):
        if discovery_type in ['all', 'usb']:
            result = await discover_serial(app, factory)
            if result:
                LOGGER.info(f'discovered usb {result[0]}')
                return result

        if discovery_type in ['all', 'wifi']:
            result = await discover_tcp(app, factory)
            if result:
                LOGGER.info(f'discovered wifi {result[0]}')
                return result

        await asyncio.sleep(DISCOVER_INTERVAL_S)

    exit_discovery()


class SparkConduit(features.ServiceFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)

        self._connection_task: asyncio.Task = None
        self._active: asyncio.Event = None

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

    @property
    def event_callbacks(self):
        return self._event_callbacks

    @property
    def data_callbacks(self):
        return self._data_callbacks

    async def startup(self, app: web.Application):
        await self.shutdown()
        self._active = asyncio.Event()

        def factory():
            return SparkProtocol(
                on_event=partial(self._do_callbacks, self._event_callbacks),
                on_data=partial(self._do_callbacks, self._data_callbacks)
            )

        if app['config']['device_serial']:
            connect_func = partial(connect_serial, self.app, factory)
        elif app['config']['device_host']:
            connect_func = partial(connect_tcp, self.app, factory)
        else:
            connect_func = partial(connect_discovered, self.app, factory)

        self._active.set()
        self._connection_task = await scheduler.create_task(
            self.app,
            self._maintain_connection(connect_func)
        )

    async def shutdown(self, *_):
        await scheduler.cancel_task(self.app, self._connection_task)
        self._connection_task = None
        self._active = None

    async def pause(self):
        if self._active:
            self._active.clear()
        if self._transport:
            self._transport.close()

    async def resume(self):
        if self._active:
            self._active.set()

    async def write(self, data: str):
        return await self.write_encoded(data.encode())

    async def write_encoded(self, data: bytes):
        if not self.connected:
            raise exceptions.NotConnected(f'{self} not connected')
        LOGGER.debug(f'{self} writing: {data}')
        self._transport.write(data + b'\n')

    def _do_callbacks(self, callbacks: List[MessageCallback_], message: str):
        async def call_cb(cb: MessageCallback_, message: str):
            try:
                await cb(self, message)
            except Exception as ex:
                warnings.warn(f'Unhandled exception in {cb}, message={message}, ex={ex}')

        loop = asyncio.get_event_loop()
        for cb in callbacks or [_default_on_message]:
            loop.create_task(call_cb(cb, message))

    async def _maintain_connection(self, connect_func: Callable[[], Awaitable[ConnectionResult_]]):
        last_ok = True
        while True:
            try:
                await self._active.wait()
                spark_status = status.get_status(self.app)
                self._address, self._transport, self._protocol = await connect_func()

                await self._protocol.connected
                await spark_status.on_connect(self._address)
                LOGGER.info(f'Connected {self}')
                last_ok = True

                if not self._active.is_set():  # pragma: no cover
                    self._transport.close()

                await self._protocol.disconnected
                await spark_status.on_disconnect()
                LOGGER.info(f'Disconnected {self}')

            except CancelledError:
                with suppress(Exception):
                    await self._transport.close()
                break

            except Exception as ex:
                if last_ok:
                    LOGGER.info(f'Connection failed: {type(ex).__name__}({ex})')
                    last_ok = False
                await asyncio.sleep(RETRY_INTERVAL_S)

            finally:
                # Keep last known address
                self._transport = None
                self._protocol = None


class SparkProtocol(asyncio.Protocol):
    def __init__(self,
                 on_event: Callable[[str], Any],
                 on_data: Callable[[str], Any]
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
            warnings.warn(f'Protocol connection error: {exc}')

    def data_received(self, data):
        self._buffer += data.decode()

        # Annotations use < and > as start/end characters
        # Most annotations can be discarded, except for event messages
        # Event messages are annotations that start with !
        for msg in self._coerce_message_from_buffer(start='<', end='>'):
            if msg.startswith('!'):  # Event
                self._on_event(msg[1:])
            else:
                LOGGER.info(f'Spark log: {msg}')

        # Once annotations are filtered, all that remains is data
        # Data is newline-separated
        for data in self._coerce_message_from_buffer(start='^', end='\n'):
            self._on_data(data)

    def _coerce_message_from_buffer(self, start: str, end: str):
        """ Filters separate messages from the buffer.

        It makes some assumptions about messages:
        * They have a fixed start/end special character
        * Start/end characters should not be included in yielded messages
        * Messages do not include start/end characters of other message types
        * Messages can be nested

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
            messages.append(msg)
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
    allowed: Iterable[DeviceMatch] = KNOWN_DEVICES,
    serial_number: str = None
) -> Iterator[PortType_]:

    # Construct a regex OR'ing all allowed hardware ID matches
    # Example result: (?:HWID_REGEX_ONE|HWID_REGEX_TWO)
    matcher = f'(?:{"|".join([dev.hwid for dev in allowed])})'

    for port in list_ports.grep(matcher):
        if serial_number is None or serial_number == port.serial_number:
            yield port


def detect_device(device: str = None, serial_number: str = None) -> str:
    if device is None:
        try:
            port = next(recognized_ports(serial_number=serial_number))
            device = port.device
            LOGGER.info(f'Automatically detected {[v for v in port]}')
        except StopIteration:
            raise exceptions.ConnectionImpossible(
                f'Could not find recognized device. Known={[{v for v in p} for p in all_ports()]}')

    return device
