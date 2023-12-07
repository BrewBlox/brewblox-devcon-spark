"""
Stores sid/nid relations for blocks
"""

import asyncio
import logging
import warnings
from contextlib import suppress
from contextvars import ContextVar

from httpx import AsyncClient

from . import const, utils
from .datastore import STORE_URL, FlushedStore
from .models import StoreEntry
from .twinkeydict import TwinKeyDict, TwinKeyError

BLOCK_STORE_KEY = '{id}-blocks-db'
READY_TIMEOUT_S = 60

SYS_OBJECTS = [
    {'keys': keys, 'data': {}}
    for keys in const.SYS_OBJECT_KEYS
]

LOGGER = logging.getLogger(__name__)
CV: ContextVar['ServiceBlockStore'] = ContextVar('block_store.ServiceBlockStore')


class ServiceBlockStore(FlushedStore, TwinKeyDict[str, int, dict]):
    """
    TwinKeyDict subclass to periodically flush contained objects to Redis.
    """

    def __init__(self, defaults: list[StoreEntry]):
        self: TwinKeyDict[str, int, dict]
        FlushedStore.__init__(self)
        TwinKeyDict.__init__(self)

        self.key: str = None
        self._defaults = defaults
        self._ready_event = asyncio.Event()
        self._client = AsyncClient(base_url=STORE_URL)

        self.clear()  # inserts defaults

    def __str__(self):
        return f'<{type(self).__name__}>'

    async def read(self, device_id: str):
        key = BLOCK_STORE_KEY.format(id=device_id)
        data = []

        try:
            self.key = None
            self._ready_event.clear()
            resp = await self._client.post('/get', json={
                'id': key,
                'namespace': const.SPARK_NAMESPACE,
            })
            self.key = key
            content_value = resp.json().get('value') or {}
            data = content_value.get('data') or []
            LOGGER.info(f'{self} Read {len(data)} blocks')

        except asyncio.CancelledError:  # pragma: no cover
            raise

        except Exception as ex:
            warnings.warn(f'{self} read error {utils.strex(ex)}')

        finally:
            # Clear -> load from database -> merge defaults
            TwinKeyDict.clear(self)
            for obj in data:
                TwinKeyDict.__setitem__(self, obj['keys'], obj['data'])
            for obj in self._defaults:
                with suppress(TwinKeyError):
                    if obj['keys'] not in self:
                        self.__setitem__(obj['keys'], obj['data'])

            self._ready_event.set()

    async def write(self):
        await asyncio.wait_for(self._ready_event.wait(), READY_TIMEOUT_S)
        if self.key is None:
            raise RuntimeError('Document key not set - did read() fail?')
        data: list[StoreEntry] = [
            {'keys': keys, 'data': content}
            for keys, content in self.items()
        ]
        await self._client.post('/set', json={
            'value': {
                'id': self.key,
                'namespace': const.SPARK_NAMESPACE,
                'data': data,
            },
        })
        LOGGER.info(f'{self} Saved {len(data)} block(s)')

    def __setitem__(self, keys, item):
        TwinKeyDict.__setitem__(self, keys, item)
        self.set_changed()

    def __delitem__(self, keys):
        TwinKeyDict.__delitem__(self, keys)
        self.set_changed()

    def clear(self):
        TwinKeyDict.clear(self)
        for obj in self._defaults:
            self.__setitem__(obj['keys'], obj['data'])


def setup():
    CV.set(ServiceBlockStore(defaults=SYS_OBJECTS))
