"""
Implements a protocol and a conduit for async serial communication.
"""

import asyncio
from asyncio import CancelledError
from contextlib import suppress
from typing import Awaitable, Callable, List, Set

from aiohttp import web
from brewblox_service import brewblox_logger, features, mqtt, repeater

from brewblox_devcon_spark import (cbox_parser, connection, exceptions,
                                   service_status)

MessageCallback_ = Callable[['SparkConduit', str], Awaitable]

LOGGER = brewblox_logger(__name__)

BASE_RETRY_INTERVAL_S = 2
MAX_RETRY_INTERVAL_S = 30
CONNECT_RETRY_COUNT = 20


class PublishedConnectSettings(features.ServiceFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)
        self._volatile = app['config']['volatile']
        self._topic = '__spark/internal/connect/' + app['config']['name']
        self._retry_interval = BASE_RETRY_INTERVAL_S

    async def startup(self, app: web.Application):
        if self._volatile:
            return
        await mqtt.listen(app, self._topic, self._on_event_message)
        await mqtt.subscribe(app, self._topic)

    async def shutdown(self, app: web.Application):
        if self._volatile:
            return
        with suppress(ValueError):
            await mqtt.unsubscribe(app, self._topic)
        with suppress(ValueError):
            await mqtt.unlisten(app, self._topic, self._on_event_message)

    async def _on_event_message(self, topic: str, message: dict):
        message = message or {}
        self._retry_interval = int(message.get('retry_interval', BASE_RETRY_INTERVAL_S))
        LOGGER.info(f'Connection retry interval is now {self._retry_interval}s')

    async def _publish(self, interval: float):
        if self._volatile:
            return
        await mqtt.publish(self.app,
                           self._topic,
                           retain=True,
                           err=False,
                           message={
                               'retry_interval': interval,
                           })

    def get_retry_interval(self):
        return self._retry_interval

    async def reset_retry_interval(self):
        await self._publish(BASE_RETRY_INTERVAL_S)

    async def increase_retry_interval(self):
        interval = min(MAX_RETRY_INTERVAL_S, round(1.5 * self._retry_interval))
        await self._publish(interval)


class ConnectionRetryExhausted(ConnectionError):
    pass


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
        settings = get_settings(self.app)

        try:
            if self._retry_count > CONNECT_RETRY_COUNT:
                raise ConnectionRetryExhausted()

            if self._retry_count > 0:
                await asyncio.sleep(settings.get_retry_interval())
                LOGGER.info('Retrying connection...')

            await service_status.wait_autoconnecting(self.app)
            self._address, self._reader, self._writer = await connection.connect(self.app)
            self._parser = cbox_parser.ControlboxParser()

            service_status.set_connected(self.app, self._address)
            self._retry_count = 0
            await settings.reset_retry_interval()
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

        except ConnectionRetryExhausted:
            LOGGER.error('Connection retry attempts exhausted. Exiting now.')
            await settings.increase_retry_interval()
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
    features.add(app, PublishedConnectSettings(app))


def get_conduit(app: web.Application) -> SparkConduit:
    return features.get(app, SparkConduit)


def get_settings(app: web.Application) -> PublishedConnectSettings:
    return features.get(app, PublishedConnectSettings)
