"""
Stores sid/nid relations for blocks
"""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from contextvars import ContextVar

from httpx import AsyncClient

from .. import const, utils
from ..models import (DatastoreSingleQuery, TwinKeyEntriesBox,
                      TwinKeyEntriesValue, TwinKeyEntry)
from ..twinkeydict import TwinKeyDict, TwinKeyError

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

    def __str__(self):
        return f'<{type(self).__name__}>'

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

        except Exception as ex:
            LOGGER.warning(f'Load error {utils.strex(ex)}', exc_info=self.config.debug)

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

    async def run(self, delayed: bool):
        if delayed:
            await self._changed_ev.wait()
            await asyncio.sleep(self.config.datastore_flush_delay.total_seconds())
        elif not self._changed_ev.is_set():
            return

        await self.save()
        self._changed_ev.clear()

    async def repeat(self):
        while True:
            try:
                await self.run(True)
            except Exception as ex:
                LOGGER.error(utils.strex(ex), exc_info=self.config.debug)
            except asyncio.CancelledError as cancel_ex:
                try:
                    await asyncio.wait_for(self.run(False),
                                           timeout=self.config.datastore_shutdown_timeout.total_seconds())
                except Exception as ex:
                    LOGGER.error(utils.strex(ex), exc_info=self.config.debug)
                raise cancel_ex

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
    async with utils.task_context(CV.get().repeat()):
        yield


def setup():
    CV.set(BlockStore(defaults=SYS_OBJECTS))
