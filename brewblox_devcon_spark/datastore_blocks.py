"""
Stores sid/nid relations for blocks
"""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from contextvars import ContextVar

from httpx import AsyncClient

from . import const, utils
from .models import (DatastoreSingleQuery, TwinKeyEntriesBox,
                     TwinKeyEntriesValue, TwinKeyEntry)
from .twinkeydict import TwinKeyDict, TwinKeyError

SYS_OBJECTS: list[TwinKeyEntry] = [
    TwinKeyEntry(keys=keys, data={})
    for keys in const.SYS_OBJECT_KEYS
]

LOGGER = logging.getLogger(__name__)

CV: ContextVar['BlockStore'] = ContextVar('block_store.BlockStore')


class BlockStore(TwinKeyDict[str, int, dict]):
    def __init__(self, defaults: list[TwinKeyEntry]):
        super().__init__()

        self.config = utils.get_config()
        self._changed_ev = asyncio.Event()
        self._doc_id: str = None
        self._defaults = defaults
        self._client = AsyncClient(base_url=self.config.datastore_url)

        self.clear()  # inserts defaults

    async def load(self, device_id: str):
        doc_id = f'{device_id}-blocks-db'
        data: list[TwinKeyEntry] = []

        try:
            self._doc_id = None

            query = DatastoreSingleQuery(id=doc_id,
                                         namespace=const.SERVICE_NAMESPACE)
            content = query.model_dump(mode='json')
            resp = await utils.httpx_retry(lambda: self._client.post('/get', json=content))

            try:
                box = TwinKeyEntriesBox.model_validate_json(resp.text)
                data = box.value.data
            except (AttributeError, ValueError):
                data = []
            LOGGER.info(f'Loaded {len(data)} block(s)')

        finally:
            # Clear -> load from database -> merge defaults
            super().clear()
            for obj in data:
                super().__setitem__(obj.keys, obj.data)
            for obj in self._defaults:
                with suppress(TwinKeyError):
                    if obj.keys not in self:
                        self.__setitem__(obj.keys, obj.data)

            self._doc_id = doc_id

    async def save(self):
        if not self._doc_id:
            raise ValueError('Document ID not set - did you forget to call load()?')

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
        LOGGER.info(f'Saved {len(data)} block(s)')
        self._changed_ev.clear()

    async def repeat(self):
        while True:
            try:
                await self._changed_ev.wait()
                await asyncio.sleep(self.config.datastore_flush_delay.total_seconds())
                await self.save()
            except Exception as ex:  # pragma: no cover
                LOGGER.error(utils.strex(ex), exc_info=self.config.debug)

    async def on_shutdown(self):
        if not self._doc_id or not self._changed_ev.is_set():
            return

        try:
            await asyncio.wait_for(self.save(),
                                   timeout=self.config.datastore_shutdown_timeout.total_seconds())
        except Exception as ex:  # pragma: no cover
            LOGGER.error(utils.strex(ex), exc_info=self.config.debug)

    def __setitem__(self, keys: tuple[str, int], item: dict):
        super().__setitem__(keys, item)
        self._changed_ev.set()

    def __delitem__(self, keys: tuple[str | None, int | None]):
        super().__delitem__(keys)
        self._changed_ev.set()

    def clear(self):
        super().clear()
        for obj in self._defaults:
            self.__setitem__(obj.keys, obj.data)


@asynccontextmanager
async def lifespan():
    store = CV.get()
    async with utils.task_context(store.repeat()):
        yield
    await store.on_shutdown()


def setup():
    CV.set(BlockStore(defaults=SYS_OBJECTS))
