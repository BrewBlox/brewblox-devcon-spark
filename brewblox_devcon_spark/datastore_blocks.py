"""
Stores sid/nid relations for blocks
"""
import asyncio
import logging
from contextlib import suppress
from contextvars import ContextVar

from httpx import AsyncClient

from . import const, exceptions, state_machine, utils
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
        self.state = state_machine.CV.get()
        self._changed_ev = asyncio.Event()
        self._flush_lock = asyncio.Lock()
        self._defaults = defaults
        self._client = AsyncClient(base_url=self.config.datastore_url)
        self._doc_id: str | None = None

    def get_doc_id(self) -> str | None:
        if not self.state.is_acknowledged():
            return None

        # Simulation services are identified by service name.
        # This prevents data conflicts when a simulation service
        # is reconfigured to start interacting with a controller.
        desc = self.state.desc()
        if desc.connection_kind == 'SIM':
            device_name = f'simulator__{self.config.name}'
        elif desc.connection_kind == 'MOCK':
            device_name = f'mock__{self.config.name}'
        else:
            device_name = desc.controller.device.device_id

        return f'{device_name}-blocks-db'

    async def load(self):
        self._doc_id = self.get_doc_id()
        data: list[TwinKeyEntry] = []

        if not self._doc_id:
            raise exceptions.NotConnected('Not acknowledged before loading block store')

        try:
            query = DatastoreSingleQuery(id=self._doc_id,
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

            self._changed_ev.clear()

    async def flush(self):
        if not self._doc_id:
            raise exceptions.NotConnected('Not acknowledged before flushing block store')

        async with self._flush_lock:
            if not self._changed_ev.is_set():
                return

            box = TwinKeyEntriesBox(
                value=TwinKeyEntriesValue(
                    id=self._doc_id,
                    namespace=const.SERVICE_NAMESPACE,
                    data=[TwinKeyEntry(keys=k, data=v)
                          for k, v in self.items()]
                )
            )
            self._changed_ev.clear()
            await self._client.post('/set',
                                    json=box.model_dump(mode='json'))
            LOGGER.info(f'Saved {len(box.value.data)} block(s)')

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


def setup():
    CV.set(BlockStore(defaults=SYS_OBJECTS))
