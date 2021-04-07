"""
Implements async serial connection.
"""

import asyncio
from contextlib import suppress
from subprocess import Popen
from typing import Callable, Set

from aiohttp import web
from brewblox_service import brewblox_logger, features, repeater

from brewblox_devcon_spark import (cbox_parser, commands, connect_funcs, const,
                                   exceptions, service_status, service_store)

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

        self._proc: Popen = None
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
            with service_store.fget(self.app).open() as config:
                self._retry_interval = config.get('retry_interval', BASE_RETRY_INTERVAL_S)
        return self._retry_interval

    @retry_interval.setter
    def retry_interval(self, value: float):
        with service_store.fget(self.app).open() as config:
            config['retry_interval'] = value
        self._retry_interval = value

    def reset_retry_interval(self):
        self.retry_interval = BASE_RETRY_INTERVAL_S

    def increase_retry_interval(self):
        self.retry_interval = min(MAX_RETRY_INTERVAL_S, round(1.5 * self.retry_interval))

    def _on_event(self, msg: str):
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

    def _on_data(self, msg: str):
        for cb in self._data_callbacks:
            cb(msg)

    async def prepare(self):
        """Implements RepeaterFeature.prepare"""
        pass

    async def run(self):
        """Implements RepeaterFeature.run"""
        try:
            if self._retry_count >= CONNECT_RETRY_COUNT:
                raise ConnectionAbortedError()
            if self._retry_count == 1:
                LOGGER.info('Retrying connection...')
            if self._retry_count > 0:
                await asyncio.sleep(self.retry_interval)

            await service_status.wait_autoconnecting(self.app)
            result = await connect_funcs.connect(self.app)
            self._proc = result.process
            self._address = result.address
            self._reader = result.reader
            self._writer = result.writer
            self._parser = cbox_parser.ControlboxParser()

            service_status.set_connected(self.app, self._address)
            self._retry_count = 0
            self.reset_retry_interval()
            LOGGER.info(f'{self} connected')

            while self.connected:
                # read() does not raise an exception when connection is closed
                # connected status must be checked explicitly later
                recv = await self._reader.read(100)

                # read() returns empty if EOF received
                if not recv:  # pragma: no cover
                    raise ConnectionError('EOF received')

                # Send to parser
                self._parser.push(recv.decode())

                # Drain parsed messages
                for msg in self._parser.event_messages():
                    self._on_event(msg)
                for msg in self._parser.data_messages():
                    self._on_data(msg)

            raise ConnectionError('Connection closed')

        except asyncio.CancelledError:
            raise

        except ConnectionAbortedError:
            LOGGER.error('Connection aborted. Exiting now.')
            self.increase_retry_interval()
            raise web.GracefulExit()

        except connect_funcs.DiscoveryAbortedError as ex:
            LOGGER.error('Device discovery failed.')
            if ex.reboot_required:
                self._retry_count += 1
            raise ex

        except Exception:
            self._retry_count += 1
            raise

        finally:
            with suppress(Exception):
                self._writer.close()
                LOGGER.info(f'{self} closed stream writer')

            with suppress(Exception):
                self._proc.terminate()
                LOGGER.info(f'{self} terminated subprocess')

            service_status.set_disconnected(self.app)
            self._proc = None
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
