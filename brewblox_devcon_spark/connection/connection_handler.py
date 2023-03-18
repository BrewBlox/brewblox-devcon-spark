import asyncio
from contextlib import suppress
from typing import Callable, Union

from aiohttp import web
from async_timeout import timeout
from brewblox_service import brewblox_logger, features, repeater, strex

from brewblox_devcon_spark import exceptions, service_status, service_store
from brewblox_devcon_spark.models import (ControllerDescription,
                                          DeviceDescription,
                                          FirmwareDescription,
                                          HandshakeMessage, ServiceConfig)

from .connection_impl import ConnectionCallbacks, ConnectionImpl
from .mock_connection import connect_mock
from .mqtt_connection import MqttDeviceTracker
from .stream_connection import (connect_serial, connect_simulation,
                                connect_tcp, discover_serial, discover_tcp)

MessageCallback_ = Callable[[str], None]

LOGGER = brewblox_logger(__name__)

BASE_RETRY_INTERVAL_S = 2
MAX_RETRY_INTERVAL_S = 30
MAX_RETRY_COUNT = 20

WELCOME_PREFIX = '!BREWBLOX'
DISCOVERY_INTERVAL_S = 5
DISCOVERY_TIMEOUT_S = 120


def increased_interval(value: float) -> float:
    if value:
        return min(MAX_RETRY_INTERVAL_S, round(1.5 * value))
    else:
        return BASE_RETRY_INTERVAL_S


async def discover(app: web.Application, callbacks: ConnectionCallbacks) -> ConnectionImpl:
    config: ServiceConfig = app['config']

    discovery_type = config['discovery']
    LOGGER.info(f'Discovering devices... ({discovery_type})')

    try:
        async with timeout(DISCOVERY_TIMEOUT_S):
            if discovery_type in ['all', 'usb']:
                result = await discover_serial(app, callbacks)
                if result:
                    return result

            if discovery_type in ['all', 'wifi', 'lan']:
                result = await discover_tcp(app, callbacks)
                if result:
                    return result

            if discovery_type in ['all', 'mqtt']:
                tracker: MqttDeviceTracker = features.get(app, MqttDeviceTracker)
                result = await tracker.discover(callbacks)
                if result:
                    return result

            await asyncio.sleep(DISCOVERY_INTERVAL_S)

    except TimeoutError:
        raise ConnectionAbortedError()


async def connect(app: web.Application, callbacks: ConnectionCallbacks) -> ConnectionImpl:
    config: ServiceConfig = app['config']

    mock = config['mock']
    simulation = config['simulation']
    device_serial = config['device_serial']
    device_host = config['device_host']
    device_port = config['device_port']

    if mock:
        return await connect_mock(app, callbacks)
    elif simulation:
        return await connect_simulation(app, callbacks)
    elif device_serial:
        return await connect_serial(device_serial, callbacks)
    elif device_host:
        return await connect_tcp(device_host, device_port, callbacks)
    else:
        return await discover(app, callbacks)


class ConnectionHandler(repeater.RepeaterFeature, ConnectionCallbacks):
    def __init__(self, app: web.Application):
        super().__init__(app)

        self._retry_count: int = 0
        self._connection: ConnectionImpl = None

        self._response_callbacks: set[MessageCallback_] = set()

    def __str__(self):
        return f'<{type(self).__name__} for {self._connection}>'

    @property
    def connected(self) -> bool:
        return self._connection is not None \
            and self._connection.connected.is_set()

    @property
    def response_callbacks(self) -> set[MessageCallback_]:
        return self._response_callbacks

    @property
    def _reconnect_interval(self) -> float:
        return service_store.get_reconnect_interval(self.app)

    @_reconnect_interval.setter
    def _reconnect_interval(self, value: float):
        service_store.set_reconnect_interval(self.app, value)

    async def on_event(self, msg: str):
        if msg.startswith(WELCOME_PREFIX):
            handshake = HandshakeMessage(*msg[1:].split(','))
            LOGGER.info(handshake)

            desc = ControllerDescription(
                system_version=handshake.system_version,
                platform=handshake.platform,
                reset_reason=handshake.reset_reason,
                firmware=FirmwareDescription(
                    firmware_version=handshake.firmware_version,
                    proto_version=handshake.proto_version,
                    firmware_date=handshake.firmware_date,
                    proto_date=handshake.proto_date,
                ),
                device=DeviceDescription(
                    device_id=handshake.device_id,
                ),
            )
            service_status.set_acknowledged(self.app, desc)

        else:
            LOGGER.info(f'Spark log: `{msg}`')

    async def on_response(self, msg: str):
        for cb in self._response_callbacks:
            await cb(msg)

    async def before_shutdown(self, app: web.Application):
        await self.end()

    async def run(self):
        """Implements RepeaterFeature.run"""
        try:
            if self._retry_count >= MAX_RETRY_COUNT:
                raise ConnectionAbortedError()

            await asyncio.sleep(self._reconnect_interval)
            await service_status.wait_enabled(self.app)

            self._connection = await connect(self.app, self)
            await self._connection.connected.wait()

            service_status.set_connected(self.app,
                                         self._connection.kind,
                                         self._connection.address)

            self._retry_count = 0
            self._reconnect_interval = 0

            await self._connection.disconnected.wait()

        except ConnectionAbortedError:
            LOGGER.error('Connection aborted. Shutting down...')
            self._reconnect_interval = increased_interval(self._reconnect_interval)

            # New USB devices require a container restart to be detected
            raise web.GracefulExit()

        except Exception as ex:
            LOGGER.debug(f'Connection error: {strex(ex)}')
            self._retry_count += 1
            raise

        finally:
            with suppress(Exception):
                await self._connection.close()

            service_status.set_disconnected(self.app)

    async def send_request(self, msg: Union[str, bytes]):
        if not self.connected:
            raise exceptions.NotConnected(f'{self} not connected')

        LOGGER.debug(f'{self} sending: {msg}')
        await self._connection.send_request(msg)

    async def start_reconnect(self):
        # The run() function will handle cleanup, and then reconnect
        if self._connection:
            await self._connection.close()
