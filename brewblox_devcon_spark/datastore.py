"""
Base class for persistent data stores
"""

import asyncio
import warnings
from abc import abstractmethod
from contextlib import suppress
from functools import wraps

from aiohttp import web
from brewblox_service import brewblox_logger, http, repeater, strex

LOGGER = brewblox_logger(__name__)

NAMESPACE = 'spark-service'
STORE_URL = 'http://history:5000/history/datastore'
RETRY_INTERVAL_S = 1
FLUSH_DELAY_S = 5
SHUTDOWN_WRITE_TIMEOUT_S = 2


def non_volatile(func):
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        if self.volatile:
            return
        return await func(self, *args, **kwargs)
    return wrapper


async def check_remote(app: web.Application):
    if app['config']['volatile']:
        return
    num_attempts = 0
    while True:
        try:
            await http.session(app).get(f'{STORE_URL}/ping')
            return
        except asyncio.CancelledError:  # pragma: no cover
            raise
        except Exception as ex:
            LOGGER.error(strex(ex))
            num_attempts += 1
            if num_attempts % 10 == 0:
                LOGGER.info(f'Waiting for datastore... ({strex(ex)})')
            await asyncio.sleep(RETRY_INTERVAL_S)


class FlushedStore(repeater.RepeaterFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)
        self._volatile = app['config']['volatile']
        self._changed_event: asyncio.Event = None

    @property
    def volatile(self):
        return self._volatile

    def set_changed(self):
        if self._changed_event:
            self._changed_event.set()

    async def before_shutdown(self, app: web.Application):
        await super().before_shutdown(app)
        await self.end()
        with suppress(Exception):
            if self._changed_event.is_set():
                LOGGER.info(f'Writing data while closing {self}')
                await asyncio.wait_for(self.write(), timeout=SHUTDOWN_WRITE_TIMEOUT_S)
        self._changed_event = None

    async def prepare(self):
        self._changed_event = asyncio.Event()
        if self._volatile:
            LOGGER.info(f'{self} is volatile (will not read/write datastore)')
            raise repeater.RepeaterCancelled()

    async def run(self):
        try:
            await self._changed_event.wait()
            await asyncio.sleep(FLUSH_DELAY_S)
            await self.write()
            self._changed_event.clear()

        except asyncio.CancelledError:
            raise

        except Exception as ex:
            warnings.warn(f'{self} flush error {strex(ex)}')

    @abstractmethod
    async def write(self):
        """
        Must be implemented by child classes.
        FlushedStore handles how and when write() is called.
        """
