import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from contextvars import ContextVar
from datetime import timedelta

from .. import exceptions, service_status, utils
from ..datastore import settings_store
from ..models import DiscoveryType
from .connection_impl import ConnectionCallbacks, ConnectionImplBase
from .mock_connection import connect_mock
from .mqtt_connection import discover_mqtt
from .stream_connection import (connect_simulation, connect_tcp, connect_usb,
                                discover_mdns, discover_usb)

BASE_RECONNECT_DELAY = timedelta(seconds=2)
MAX_RECONNECT_DELAY = timedelta(seconds=30)
MAX_RETRY_COUNT = 20

DISCOVERY_INTERVAL = timedelta(seconds=5)
DISCOVERY_TIMEOUT = timedelta(seconds=120)

LOGGER = logging.getLogger(__name__)

CV: ContextVar['ConnectionHandler'] = ContextVar('connection_handler.ConnectionHandler')


def calc_backoff(value: timedelta | None) -> timedelta:
    if value:
        return min(value * 1.5, MAX_RECONNECT_DELAY)
    else:
        return BASE_RECONNECT_DELAY


class ConnectionHandler(ConnectionCallbacks):
    def __init__(self):
        self._delay: timedelta = BASE_RECONNECT_DELAY
        self._attempts: int = 0
        self._impl: ConnectionImplBase = None

    def __str__(self):
        return f'<{type(self).__name__} for {self._impl}>'

    @property
    def connected(self) -> bool:
        return self._impl is not None \
            and self._impl.connected.is_set()

    @property
    def usb_compatible(self) -> bool:
        config = utils.get_config()

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
        config = utils.get_config()

        discovery_type = config.discovery
        LOGGER.info(f'Discovering devices... ({discovery_type})')

        try:
            async with asyncio.timeout(DISCOVERY_TIMEOUT.total_seconds()):
                while True:
                    if discovery_type in [DiscoveryType.all, DiscoveryType.usb]:
                        result = await discover_usb(self)
                        if result:
                            return result

                    if discovery_type in [DiscoveryType.all, DiscoveryType.mdns]:
                        result = await discover_mdns(self)
                        if result:
                            return result

                    if discovery_type in [DiscoveryType.all, DiscoveryType.mqtt]:
                        result = await discover_mqtt(self)
                        if result:
                            return result

                    await asyncio.sleep(DISCOVERY_INTERVAL.total_seconds())

        except asyncio.TimeoutError:
            raise ConnectionAbortedError('Discovery timeout')

    async def connect(self) -> ConnectionImplBase:
        config = utils.get_config()

        mock = config.mock
        simulation = config.simulation
        device_serial = config.device_serial
        device_host = config.device_host
        device_port = config.device_port

        if mock:
            return await connect_mock(self)
        elif simulation:
            return await connect_simulation(self)
        elif device_serial:
            return await connect_usb(self, device_serial)
        elif device_host:
            return await connect_tcp(self, device_host, device_port)
        else:
            return await self.discover()

    async def run(self):
        status = service_status.CV.get()
        store = settings_store.CV.get()

        try:
            if self._attempts > MAX_RETRY_COUNT:
                raise ConnectionAbortedError('Retry attempts exhausted')

            await asyncio.sleep(self._delay.total_seconds())
            await status.wait_enabled()

            self._impl = await self.connect()
            await self._impl.connected.wait()

            status.set_connected(self._impl.kind,
                                 self._impl.address)

            self._attempts = 0
            self._delay = BASE_RECONNECT_DELAY

            await self._impl.disconnected.wait()
            raise ConnectionError('Disconnected')

        except ConnectionAbortedError as ex:
            LOGGER.error(utils.strex(ex))
            self._delay = calc_backoff(self._delay)

            # USB devices that were plugged in after container start are not visible
            # If we are potentially connecting to a USB device, we need to restart
            if self.usb_compatible:
                await store.commit_service_settings()
                utils.graceful_shutdown()
            else:
                self._attempts = 0

        except Exception as ex:
            self._attempts += 1
            if self._attempts == 1:
                LOGGER.error(utils.strex(ex))
            else:
                LOGGER.debug(utils.strex(ex), exc_info=True)

        finally:
            with suppress(Exception):
                await self._impl.close()
            status.set_disconnected()

    async def repeat(self):
        config = utils.get_config()
        while True:
            try:
                await self.run()
            except Exception as ex:
                LOGGER.error(utils.strex(ex), exc_info=config.debug)

    async def send_request(self, msg: str):
        if not self.connected:
            raise exceptions.NotConnected(f'{self} not connected')

        await self._impl.send_request(msg)

    async def start_reconnect(self):
        # The run() function will handle cleanup, and then reconnect
        if self._impl:
            await self._impl.close()


@asynccontextmanager
async def lifespan():
    handler = CV.get()
    task = asyncio.create_task(handler.repeat())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


def setup():
    CV.set(ConnectionHandler())
