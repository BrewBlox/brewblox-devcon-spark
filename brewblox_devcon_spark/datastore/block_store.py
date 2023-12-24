"""
Stores sid/nid relations for blocks
"""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from contextvars import ContextVar
from datetime import timedelta

from httpx import AsyncClient

from .. import const, utils
from ..models import (DatastoreSingleQuery, TwinKeyEntriesBox,
                      TwinKeyEntriesValue, TwinKeyEntry)
from ..twinkeydict import TwinKeyDict, TwinKeyError

FLUSH_DELAY = timedelta(seconds=5)
SHUTDOWN_WRITE_TIMEOUT = timedelta(seconds=2)
READY_TIMEOUT = timedelta(minutes=1)

SYS_OBJECTS: list[TwinKeyEntry] = [
    TwinKeyEntry(keys=keys, data={})
    for keys in const.SYS_OBJECT_KEYS
]

LOGGER = logging.getLogger(__name__)

CV: ContextVar['BlockStore'] = ContextVar('block_store.BlockStore')


class BlockStore(TwinKeyDict[str, int, dict]):
    def __init__(self, defaults: list[TwinKeyEntry]):
        super().__init__()

        config = utils.get_config()
        self._ready_ev = asyncio.Event()
        self._changed_ev = asyncio.Event()
        self._doc_id: str = None
        self._defaults = defaults
        self._client = AsyncClient(base_url=config.datastore_url)

        self.clear()  # inserts defaults

    def __str__(self):
        return f'<{type(self).__name__}>'

    async def load(self, device_id: str):
        config = utils.get_config()
        doc_id = f'{device_id}-blocks-db'
        data: list[TwinKeyEntry] = []

        try:
            self._doc_id = None
            self._ready_ev.clear()
            query = DatastoreSingleQuery(id=doc_id,
                                         namespace=const.SERVICE_NAMESPACE)
            content = query.model_dump(mode='json')
            resp = await utils.httpx_retry(lambda: self._client.post('/get', json=content))
            self._doc_id = doc_id
            try:
                box = TwinKeyEntriesBox.model_validate_json(resp.text)
                data = box.value.data
            except (AttributeError, ValueError):
                data = []
            LOGGER.info(f'Loaded {len(data)} block(s)')

        except Exception as ex:
            LOGGER.warn(f'Load error {utils.strex(ex)}', exc_info=config.debug)

        finally:
            # Clear -> load from database -> merge defaults
            super().clear()
            for obj in data:
                super().__setitem__(obj.keys, obj.data)
            for obj in self._defaults:
                with suppress(TwinKeyError):
                    if obj.keys not in self:
                        self.__setitem__(obj.keys, obj.data)

            self._ready_ev.set()

    async def write(self):
        await asyncio.wait_for(self._ready_ev.wait(), READY_TIMEOUT.total_seconds())
        if self._doc_id is None:
            raise RuntimeError('Document id not set - did load() fail?')

        data = [TwinKeyEntry(keys=k, data=v)
                for k, v in self.items()]
        box = TwinKeyEntriesBox(
            value=TwinKeyEntriesValue(
                id=self._doc_id,
                namespace=const.SERVICE_NAMESPACE,
                data=data
            )
        )
        await self._client.post('/set',
                                json=box.model_dump(mode='json'))
        LOGGER.info(f'{self} Saved {len(data)} block(s)')

    async def run(self, delayed: bool):
        if delayed:
            await self._changed_ev.wait()
            await asyncio.sleep(FLUSH_DELAY.total_seconds())
        elif not self._changed_ev.is_set():
            return

        await self.write()
        self._changed_ev.clear()

    async def repeat(self):
        config = utils.get_config()
        while True:
            try:
                await self.run(True)
            except Exception as ex:
                LOGGER.error(f'{self} {utils.strex(ex)}', exc_info=config.debug)
            except asyncio.CancelledError as cancel_ex:
                try:
                    await asyncio.wait_for(self.run(False),
                                           timeout=SHUTDOWN_WRITE_TIMEOUT.total_seconds())
                except Exception as ex:
                    LOGGER.error(f'{self} {utils.strex(ex)}', exc_info=config.debug)
                raise cancel_ex

    def __setitem__(self, keys, item):
        super().__setitem__(keys, item)
        self._changed_ev.set()

    def __delitem__(self, keys):
        super().__delitem__(keys)
        self._changed_ev.set()

    def clear(self):
        super().clear()
        for obj in self._defaults:
            self.__setitem__(obj.keys, obj.data)


@asynccontextmanager
async def lifespan():
    async with utils.task_context(CV.get().repeat()):
        yield


def setup():
    CV.set(BlockStore(defaults=SYS_OBJECTS))
