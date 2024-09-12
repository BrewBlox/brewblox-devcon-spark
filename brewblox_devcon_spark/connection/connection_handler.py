import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from contextvars import ContextVar
from datetime import timedelta

from .. import exceptions, state_machine, utils
from ..models import DiscoveryType
from .connection_impl import ConnectionCallbacks, ConnectionImplBase
from .mock_connection import connect_mock
from .mqtt_connection import discover_mqtt
from .stream_connection import (connect_simulation, connect_tcp, discover_mdns,
                                discover_usb)

LOGGER = logging.getLogger(__name__)

CV: ContextVar['ConnectionHandler'] = ContextVar('connection_handler.ConnectionHandler')


def calc_interval(value: timedelta | None) -> timedelta:
    config = utils.get_config()

    if value:
        return min(value * config.connect_backoff, config.connect_interval_max)
    else:
        return config.connect_interval


class ConnectionHandler(ConnectionCallbacks):
    def __init__(self):
        self.config = utils.get_config()
        self.state = state_machine.CV.get()

        self._enabled: bool = True
        self._last_ok: bool = True
        self._interval: timedelta = calc_interval(None)
        self._impl: ConnectionImplBase = None

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

    async def discover(self) -> ConnectionImplBase:
        discovery_type = self.config.discovery
        LOGGER.info(f'Discovering devices... ({discovery_type})')

        try:
            async with asyncio.timeout(self.config.discovery_timeout.total_seconds()):
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

                    await asyncio.sleep(self.config.discovery_interval.total_seconds())

        except asyncio.TimeoutError:
            raise ConnectionAbortedError('Discovery timeout')

    async def connect(self) -> ConnectionImplBase:
        mock = self.config.mock
        simulation = self.config.simulation
        device_host = self.config.device_host
        device_port = self.config.device_port

        if mock:
            return await connect_mock(self)
        elif simulation:
            return await connect_simulation(self)
        elif device_host:
            return await connect_tcp(self, device_host, device_port)
        else:
            return await self.discover()

    async def run(self):
        try:
            await self.state.wait_enabled()
            self._impl = await self.connect()
            await self._impl.connected.wait()

            self.state.set_connected(self._impl.kind,
                                     self._impl.address)

            self._last_ok = True
            self._interval = calc_interval(None)

            await self._impl.disconnected.wait()
            raise ConnectionError('Disconnected')

        except ConnectionAbortedError as ex:
            LOGGER.error(utils.strex(ex))
            self._interval = calc_interval(self._interval)

        except Exception as ex:
            if self._last_ok:
                LOGGER.error(utils.strex(ex))
                self._last_ok = False
            else:
                LOGGER.debug(utils.strex(ex), exc_info=True)

        finally:
            with suppress(Exception):
                await self._impl.close()
            self._impl = None
            self.state.set_disconnected()

    async def repeat(self):
        while self._enabled:
            try:
                await self.run()
            except Exception as ex:  # pragma: no cover
                LOGGER.error(utils.strex(ex), exc_info=self.config.debug)

            await asyncio.sleep(self._interval.total_seconds())

    async def send_request(self, msg: str):
        if not self.connected:
            raise exceptions.NotConnected()

        await self._impl.send_request(msg)

    async def reset(self):
        # The run() function will handle cleanup
        if self._impl:
            await self._impl.close()
        await self.state.wait_disconnected()

    async def end(self):
        self._enabled = False
        await self.reset()


@asynccontextmanager
async def lifespan():
    async with utils.task_context(CV.get().repeat()):
        yield


def setup():
    CV.set(ConnectionHandler())
