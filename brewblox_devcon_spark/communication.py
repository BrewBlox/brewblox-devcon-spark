"""
Implements a protocol and a conduit for async serial communication.
"""

import asyncio
from asyncio import CancelledError
from typing import Awaitable, Callable, List, Set

from aiohttp import web
from brewblox_service import brewblox_logger, features, repeater

from brewblox_devcon_spark import cbox_parser, connection, exceptions, state

MessageCallback_ = Callable[['SparkConduit', str], Awaitable]

LOGGER = brewblox_logger(__name__)

RETRY_INTERVAL_S = 2
CONNECT_RETRY_COUNT = 20


class SparkConduit(repeater.RepeaterFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)

        self._retry_count: int = 0
        self._read_timeout: float = max(app['config']['read_timeout'], 0)

        self._address: str = None
        self._reader: asyncio.StreamReader = None
        self._writer: asyncio.StreamWriter = None
        self._parser: cbox_parser.ControlboxParser = None

        self._event_callbacks = set()
        self._data_callbacks = set()

    def __str__(self):
        return f'<{type(self).__name__} for {self._address}>'

    @property
    def connected(self) -> bool:
        return bool(self._writer and not self._writer.is_closing())

    @property
    def event_callbacks(self) -> Set[MessageCallback_]:
        return self._event_callbacks

    @property
    def data_callbacks(self) -> Set[MessageCallback_]:
        return self._data_callbacks

    async def prepare(self):
        """Implements RepeaterFeature.prepare"""
        pass

    async def run(self):
        """Implements RepeaterFeature.run"""
        try:
            if self._retry_count > CONNECT_RETRY_COUNT:
                LOGGER.error('Connection retry attempts exhausted. Exiting now.')
                raise web.GracefulExit()

            if self._retry_count > 0:
                await asyncio.sleep(RETRY_INTERVAL_S)
                LOGGER.info('Retrying connection...')

            self._address, self._reader, self._writer = await connection.connect(self.app)
            self._parser = cbox_parser.ControlboxParser()

            await state.set_connect(self.app, self._address)
            self._retry_count = 0
            LOGGER.info(f'Connected {self}')

            while self.connected:
                # read() does not raise an exception when connection is closed
                # broadcaster is responsible for making enough requests to keep the connection alive
                recv = await asyncio.wait_for(self._reader.read(100), self._read_timeout)

                # Is connection closed?
                if not recv:  # pragma: no cover
                    continue

                # Send to parser
                self._parser.push(recv.decode())

                # Drain parsed messages
                for msg in self._parser.event_messages():
                    self._do_callbacks(self._event_callbacks, msg)
                for msg in self._parser.data_messages():
                    self._do_callbacks(self._data_callbacks, msg)

            raise ConnectionError('Connection closed')

        except CancelledError:
            raise

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
                await state.set_disconnect(self.app)
                self._reader = None
                self._writer = None
                self._parser = None

    def _do_callbacks(self, callbacks: List[MessageCallback_], message: str):
        async def call_cb(cb: MessageCallback_, message: str):
            try:
                await cb(self, message)
            except Exception:
                LOGGER.exception(f'Unhandled exception in {cb}, message={message}')

        for cb in callbacks:
            asyncio.create_task(call_cb(cb, message))

    async def write(self, data: str):
        return await self.write_encoded(data.encode())

    async def write_encoded(self, data: bytes):
        if not self.connected:
            raise exceptions.NotConnected(f'{self} not connected')

        LOGGER.debug(f'{self} writing: {data}')
        self._writer.write(data + b'\n')
        await self._writer.drain()


def setup(app: web.Application):
    features.add(app, SparkConduit(app))


def get_conduit(app: web.Application) -> SparkConduit:
    return features.get(app, SparkConduit)
