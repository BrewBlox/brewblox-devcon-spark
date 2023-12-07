"""
Base class for persistent data stores
"""

import asyncio
import logging
import warnings
from abc import abstractmethod
from contextlib import suppress

import httpx

from . import utils

STORE_URL = 'http://history:5000/history/datastore'
RETRY_INTERVAL_S = 1
FLUSH_DELAY_S = 5
SHUTDOWN_WRITE_TIMEOUT_S = 2

LOGGER = logging.getLogger(__name__)


async def check_remote():
    num_attempts = 0
    async with httpx.AsyncClient(base_url=STORE_URL) as client:
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
                await asyncio.sleep(RETRY_INTERVAL_S)


class FlushedStore:

    def __init__(self):
        self._changed_event = asyncio.Event()

    def set_changed(self):
        if self._changed_event:
            self._changed_event.set()

    async def before_shutdown(self):
        with suppress(Exception):
            if self._changed_event.is_set():
                LOGGER.info(f'Writing data while closing {self}')
                await asyncio.wait_for(self.write(), timeout=SHUTDOWN_WRITE_TIMEOUT_S)
        self._changed_event = None

    async def run(self):
        try:
            await self._changed_event.wait()
            await asyncio.sleep(FLUSH_DELAY_S)
            await self.write()
            self._changed_event.clear()

        except Exception as ex:
            warnings.warn(f'{self} flush error {utils.strex(ex)}')

    @abstractmethod
    async def write(self):
        """
        Must be implemented by child classes.
        FlushedStore handles how and when write() is called.
        """
