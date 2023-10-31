import asyncio
from contextlib import suppress

from aiohttp import web
from async_timeout import timeout
from brewblox_service import brewblox_logger, features, repeater, strex

from brewblox_devcon_spark import exceptions, service_status, service_store
from brewblox_devcon_spark.models import DiscoveryType, ServiceConfig

from .connection_impl import ConnectionCallbacks, ConnectionImplBase
from .mock_connection import connect_mock
from .mqtt_connection import discover_mqtt
from .stream_connection import (connect_simulation, connect_tcp, connect_usb,
                                discover_mdns, discover_usb)

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

        self._attempts: int = 0
        self._impl: ConnectionImplBase = None

    def __str__(self):
        return f'<{type(self).__name__} for {self._impl}>'

    async def before_shutdown(self, app: web.Application):
        await self.end()

    @property
    def connected(self) -> bool:
        return self._impl is not None \
            and self._impl.connected.is_set()

    @property
    def usb_compatible(self) -> bool:
        config: ServiceConfig = self.app['config']

        # Simulations (internal or external) do not use USB
        if config.mock or config.simulation:
            return False

        # Hardcoded addresses take precedence over device discovery
        if config.device_serial or config.device_host:
            return config.device_serial is not None

        # USB is explicitly enabled
        if config.discovery == DiscoveryType.usb:
            return True

        # TCP is explicitly enabled
        if config.discovery != DiscoveryType.all:
            return False

        # Spark models can be identified by device ID
        # Spark 2/3 use 12 bytes / 24 characters
        # Spark 4 uses 6 bytes / 12 characters
        # Spark simulations can have variable length IDs
        # USB should only be disabled if we're sure it is not supported
        if config.device_id and len(config.device_id) == 12:
            return False

        # We're not sure
        return True

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

    async def discover(self) -> ConnectionImplBase:
        config: ServiceConfig = self.app['config']

        discovery_type = config.discovery
        LOGGER.info(f'Discovering devices... ({discovery_type})')

        try:
            async with timeout(DISCOVERY_TIMEOUT_S):
                while True:
                    if discovery_type in [DiscoveryType.all, DiscoveryType.usb]:
                        result = await discover_usb(self.app, self)
                        if result:
                            return result

                    if discovery_type in [DiscoveryType.all, DiscoveryType.mdns]:
                        result = await discover_mdns(self.app, self)
                        if result:
                            return result

                    if discovery_type in [DiscoveryType.all, DiscoveryType.mqtt]:
                        result = await discover_mqtt(self.app, self)
                        if result:
                            return result

                    await asyncio.sleep(DISCOVERY_INTERVAL_S)

        except asyncio.TimeoutError:
            raise ConnectionAbortedError('Discovery timeout')

    async def connect(self) -> ConnectionImplBase:
        config: ServiceConfig = self.app['config']

        mock = config.mock
        simulation = config.simulation
        device_serial = config.device_serial
        device_host = config.device_host
        device_port = config.device_port

        if mock:
            return await connect_mock(self.app, self)
        elif simulation:
            return await connect_simulation(self.app, self)
        elif device_serial:
            return await connect_usb(self.app, self, device_serial)
        elif device_host:
            return await connect_tcp(self.app, self, device_host, device_port)
        else:
            return await self.discover()

    async def run(self):
        """Implements RepeaterFeature.run"""
        delay = service_store.get_reconnect_delay(self.app)

        try:
            if self._attempts > MAX_RETRY_COUNT:
                raise ConnectionAbortedError('Retry attempts exhausted')

            await asyncio.sleep(delay)
            await service_status.wait_enabled(self.app)

            self._impl = await self.connect()
            await self._impl.connected.wait()

            service_status.set_connected(self.app,
                                         self._impl.kind,
                                         self._impl.address)

            self._attempts = 0
            self._reconnect_interval = 0

            await self._impl.disconnected.wait()
            raise ConnectionError('Disconnected')

        except ConnectionAbortedError as ex:
            LOGGER.error(strex(ex))
            service_store.set_reconnect_delay(self.app, calc_backoff(delay))

            # USB devices that were plugged in after container start are not visible
            # If we are potentially connecting to a USB device, we need to restart
            if self.usb_compatible:
                raise web.GracefulExit()
            else:
                self._attempts = 0

        except Exception as ex:
            self._attempts += 1
            if self._attempts == 1:
                LOGGER.error(strex(ex))
            else:
                LOGGER.debug(strex(ex))

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
