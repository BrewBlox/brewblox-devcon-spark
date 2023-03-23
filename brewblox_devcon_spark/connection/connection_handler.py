import asyncio
from contextlib import suppress

from aiohttp import web
from async_timeout import timeout
from brewblox_service import brewblox_logger, features, repeater, strex

from brewblox_devcon_spark import exceptions, service_status, service_store
from brewblox_devcon_spark.models import ServiceConfig

from .connection_impl import ConnectionCallbacks, ConnectionImpl
from .mock_connection import connect_mock
from .mqtt_connection import discover_mqtt
from .stream_connection import (connect_serial, connect_simulation,
                                connect_tcp, discover_serial, discover_tcp)

LOGGER = brewblox_logger(__name__)

BASE_RECONNECT_DELAY_S = 2
MAX_RECONNECT_DELAY_S = 30
MAX_RETRY_COUNT = 20

DISCOVERY_INTERVAL_S = 5
DISCOVERY_TIMEOUT_S = 120


def calc_backoff(value: float) -> float:
    if value:
        return min(MAX_RECONNECT_DELAY_S, round(1.5 * value))
    else:
        return BASE_RECONNECT_DELAY_S


class ConnectionHandler(repeater.RepeaterFeature, ConnectionCallbacks):
    def __init__(self, app: web.Application):
        super().__init__(app)

        self._retry_count: int = 0
        self._impl: ConnectionImpl = None

    def __str__(self):
        return f'<{type(self).__name__} for {self._impl}>'

    async def before_shutdown(self, app: web.Application):
        await self.end()

    @property
    def connected(self) -> bool:
        return self._impl is not None \
            and self._impl.connected.is_set()

    async def on_event(self, msg: str):
        """
        This function can be replaced by whoever wants to receive
        the actual response.
        """

    async def on_response(self, msg: str):
        """
        This function can be replaced by whoever wants to receive
        the actual response.
        """

    async def discover(self) -> ConnectionImpl:
        config: ServiceConfig = self.app['config']

        discovery_type = config['discovery']
        LOGGER.info(f'Discovering devices... ({discovery_type})')

        try:
            async with timeout(DISCOVERY_TIMEOUT_S):
                while True:
                    if discovery_type in ['all', 'usb']:
                        result = await discover_serial(self.app, self)
                        if result:
                            return result

                    if discovery_type in ['all', 'wifi', 'lan']:
                        result = await discover_tcp(self.app, self)
                        if result:
                            return result

                    if discovery_type in ['all', 'mqtt']:
                        result = await discover_mqtt(self.app, self)
                        if result:
                            return result

                    await asyncio.sleep(DISCOVERY_INTERVAL_S)

        except asyncio.TimeoutError:
            raise ConnectionAbortedError()

    async def connect(self) -> ConnectionImpl:
        config: ServiceConfig = self.app['config']

        mock = config['mock']
        simulation = config['simulation']
        device_serial = config['device_serial']
        device_host = config['device_host']
        device_port = config['device_port']

        if mock:
            return await connect_mock(self.app, self)
        elif simulation:
            return await connect_simulation(self.app, self)
        elif device_serial:
            return await connect_serial(self.app, self, device_serial)
        elif device_host:
            return await connect_tcp(self.app, self, device_host, device_port)
        else:
            return await self.discover()

    async def run(self):
        """Implements RepeaterFeature.run"""
        delay = service_store.get_reconnect_delay(self.app)

        try:
            if self._retry_count > MAX_RETRY_COUNT:
                raise ConnectionAbortedError()

            await asyncio.sleep(delay)
            await service_status.wait_enabled(self.app)

            self._impl = await self.connect()
            await self._impl.connected.wait()

            service_status.set_connected(self.app,
                                         self._impl.kind,
                                         self._impl.address)

            self._retry_count = 0
            self._reconnect_interval = 0

            await self._impl.disconnected.wait()
            raise ConnectionError('Disconnected')

        # New USB devices require a container restart to be detected
        except ConnectionAbortedError:
            LOGGER.error('Connection aborted. Shutting down...')
            service_store.set_reconnect_delay(self.app, calc_backoff(delay))
            raise web.GracefulExit()

        except Exception as ex:
            if self._retry_count:
                LOGGER.debug(strex(ex))
            else:
                LOGGER.error(strex(ex))
            self._retry_count += 1

        finally:
            with suppress(Exception):
                await self._impl.close()
            service_status.set_disconnected(self.app)

    async def send_request(self, msg: str):
        if not self.connected:
            raise exceptions.NotConnected(f'{self} not connected')

        await self._impl.send_request(msg)

    async def start_reconnect(self):
        # The run() function will handle cleanup, and then reconnect
        if self._impl:
            await self._impl.close()


def setup(app: web.Application):
    features.add(app, ConnectionHandler(app))


def fget(app: web.Application) -> ConnectionHandler:
    return features.get(app, ConnectionHandler)
