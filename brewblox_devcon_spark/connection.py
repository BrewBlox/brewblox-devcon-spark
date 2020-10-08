"""
Implements async serial connection.
"""

import asyncio
from asyncio import CancelledError
from typing import Callable, Set

from aiohttp import web
from brewblox_service import brewblox_logger, features, repeater

from brewblox_devcon_spark import (cbox_parser, commands, config_store,
                                   connect_funcs, const, exceptions,
                                   service_status)

MessageCallback_ = Callable[[str], None]

LOGGER = brewblox_logger(__name__)

BASE_RETRY_INTERVAL_S = 2
MAX_RETRY_INTERVAL_S = 30
CONNECT_RETRY_COUNT = 20


class SparkConnection(repeater.RepeaterFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)

        self._retry_count: int = 0
        self._retry_interval: float = 0

        self._address: str = None
        self._reader: asyncio.StreamReader = None
        self._writer: asyncio.StreamWriter = None
        self._parser: cbox_parser.ControlboxParser = None

        self._data_callbacks = set()

    def __str__(self):
        return f'<{type(self).__name__} for {self._address}>'

    @property
    def connected(self) -> bool:
        return bool(self._writer and not self._writer.is_closing())

    @property
    def data_callbacks(self) -> Set[MessageCallback_]:
        return self._data_callbacks

    @property
    def retry_interval(self) -> float:
        if not self._retry_interval:
            with config_store.fget(self.app).open() as config:
                self._retry_interval = config.get('retry_interval', BASE_RETRY_INTERVAL_S)
        return self._retry_interval

    @retry_interval.setter
    def retry_interval(self, value: float):
        with config_store.fget(self.app).open() as config:
            config['retry_interval'] = value
        self._retry_interval = value

    def reset_retry_interval(self):
        self.retry_interval = BASE_RETRY_INTERVAL_S

    def increase_retry_interval(self):
        self.retry_interval = min(MAX_RETRY_INTERVAL_S, round(1.5 * self.retry_interval))

    def _on_event_message(self, msg: str):
        if msg.startswith(const.WELCOME_PREFIX):
            welcome = commands.HandshakeMessage(*msg.split(','))
            LOGGER.info(welcome)

            device = service_status.DeviceInfo(
                welcome.firmware_version,
                welcome.proto_version,
                welcome.firmware_date,
                welcome.proto_date,
                welcome.device_id,
                welcome.system_version,
                welcome.platform,
                welcome.reset_reason,
            )
            service_status.set_acknowledged(self.app, device)

        elif msg.startswith(const.CBOX_ERR_PREFIX):
            try:
                LOGGER.error('Spark CBOX error: ' + commands.Errorcode(int(msg[-2:], 16)).name)
            except ValueError:
                LOGGER.error('Unknown Spark CBOX error: ' + msg)

        elif msg.startswith(const.SETUP_MODE_PREFIX):
            LOGGER.error('Controller entered listening mode. Exiting service now.')
            raise web.GracefulExit()

        else:
            LOGGER.info(f'Spark event: `{msg}`')

    def _on_data_message(self, msg: str):
        for cb in self._data_callbacks:
            cb(msg)

    async def prepare(self):
        """Implements RepeaterFeature.prepare"""
        pass

    async def run(self):
        """Implements RepeaterFeature.run"""
        try:
            if self._retry_count > CONNECT_RETRY_COUNT:
                raise ConnectionAbortedError()

            if self._retry_count > 0:
                await asyncio.sleep(self.retry_interval)
                LOGGER.info('Retrying connection...')

            await service_status.wait_autoconnecting(self.app)
            self._address, self._reader, self._writer = await connect_funcs.connect(self.app)
            self._parser = cbox_parser.ControlboxParser()

            service_status.set_connected(self.app, self._address)
            self._retry_count = 0
            self.reset_retry_interval()
            LOGGER.info(f'Connected {self}')

            while self.connected:
                # read() does not raise an exception when connection is closed
                # connected status must be checked explicitly later
                recv = await self._reader.read(100)

                # Is connection closed?
                if not recv:  # pragma: no cover
                    continue

                # Send to parser
                self._parser.push(recv.decode())

                # Drain parsed messages
                for msg in self._parser.event_messages():
                    self._on_event_message(msg)
                for msg in self._parser.data_messages():
                    self._on_data_message(msg)

            raise ConnectionError('Connection closed')

        except CancelledError:
            raise

        except connect_funcs.DiscoveryAbortedError as ex:
            LOGGER.error('Device discovery failed.')
            self.increase_retry_interval()
            if ex.reboot_required:
                raise web.GracefulExit()

        except ConnectionAbortedError:
            LOGGER.error('Connection aborted. Exiting now.')
            self.increase_retry_interval()
            raise web.GracefulExit()

        except Exception:
            self._retry_count += 1
            raise

        finally:
            try:
                self._writer.close()
                LOGGER.info(f'Closed {self}')
            except Exception:
                pass
            finally:
                service_status.set_disconnected(self.app)
                self._reader = None
                self._writer = None
                self._parser = None

    async def write(self, data: str):
        return await self.write_encoded(data.encode())

    async def write_encoded(self, data: bytes):
        if not self.connected:
            raise exceptions.NotConnected(f'{self} not connected')

        LOGGER.debug(f'{self} writing: {data}')
        self._writer.write(data + b'\n')
        await self._writer.drain()

    async def start_reconnect(self):
        # The run() function will handle cleanup, and then reconnect
        if self.connected:
            self._writer.close()


def setup(app: web.Application):
    features.add(app, SparkConnection(app))


def fget(app: web.Application) -> SparkConnection:
    return features.get(app, SparkConnection)
