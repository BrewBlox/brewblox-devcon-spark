"""
Base class for persistent data stores
"""

import asyncio
import logging
from abc import abstractmethod
from contextlib import asynccontextmanager, suppress
from datetime import timedelta

import httpx

from . import utils

RETRY_INTERVAL = timedelta(seconds=1)
FLUSH_DELAY = timedelta(seconds=5)
SHUTDOWN_WRITE_TIMEOUT = timedelta(seconds=2)

LOGGER = logging.getLogger(__name__)


async def check_remote():
    config = utils.get_config()
    num_attempts = 0
    async with httpx.AsyncClient(base_url=config.datastore_url) as client:
        while True:
            try:
                resp = await client.get('/ping')
                if resp.status_code == 200:
                    return
            except Exception as ex:
                LOGGER.error(utils.strex(ex))
                num_attempts += 1
                if num_attempts % 10 == 0:
                    LOGGER.info(f'Waiting for datastore... ({utils.strex(ex)})')
                await asyncio.sleep(RETRY_INTERVAL.total_seconds())


class FlushedStore:

    def __init__(self):
        self._changed_ev = asyncio.Event()

    def set_changed(self):
        self._changed_ev.set()

    async def _run(self, delayed: bool):
        if delayed:
            await self._changed_ev.wait()
            await asyncio.sleep(FLUSH_DELAY.total_seconds())
        elif not self._changed_ev.is_set():
            return

        LOGGER.debug(f'Flushing {self} ...')
        await self.write()
        self._changed_ev.clear()

    async def _repeat(self):
        config = utils.get_config()
        while True:
            try:
                await self._run(True)
            except Exception as ex:
                LOGGER.error(f'{self} {utils.strex(ex)}', exc_info=config.debug)
            except asyncio.CancelledError as cancel_ex:
                try:
                    await asyncio.wait_for(self._run(False),
                                           timeout=SHUTDOWN_WRITE_TIMEOUT.total_seconds())
                except Exception as ex:
                    LOGGER.error(f'{self} {utils.strex(ex)}', exc_info=config.debug)
                raise cancel_ex

    @asynccontextmanager
    async def lifespan(self):
        task = asyncio.create_task(self._repeat())
        yield
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    @abstractmethod
    async def write(self):
        """
        Must be implemented by child classes.
        FlushedStore handles how and when write() is called.
        """
