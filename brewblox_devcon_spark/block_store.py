"""
Stores sid/nid relations for blocks
"""

import asyncio
import logging
import warnings
from contextlib import asynccontextmanager, suppress
from contextvars import ContextVar
from datetime import timedelta

from httpx import AsyncClient

from . import const, utils
from .datastore import FlushedStore
from .models import TwinkeyEntriesBox, TwinkeyEntriesValue, TwinkeyEntry
from .twinkeydict import TwinKeyDict, TwinKeyError

BLOCK_STORE_KEY = '{id}-blocks-db'
READY_TIMEOUT = timedelta(minutes=1)

SYS_OBJECTS: list[TwinkeyEntry] = [
    TwinkeyEntry(keys=keys, data={})
    for keys in const.SYS_OBJECT_KEYS
]

LOGGER = logging.getLogger(__name__)
CV: ContextVar['ServiceBlockStore'] = ContextVar('block_store.ServiceBlockStore')


class ServiceBlockStore(FlushedStore, TwinKeyDict[str, int, dict]):
    """
    TwinKeyDict subclass to periodically flush contained objects to Redis.
    """

    def __init__(self, defaults: list[TwinkeyEntry]):
        self: TwinKeyDict[str, int, dict]
        FlushedStore.__init__(self)
        TwinKeyDict.__init__(self)

        config = utils.get_config()
        self.key: str = None
        self._defaults = defaults
        self._ready_event = asyncio.Event()
        self._client = AsyncClient(base_url=config.datastore_url)

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
            try:
                content = TwinkeyEntriesBox.model_validate_json(resp.text)
                data = content.value.data
            except (KeyError, ValueError):
                data = []
            LOGGER.info(f'{self} Read {len(data)} blocks')

        except asyncio.CancelledError:  # pragma: no cover
            raise

        except Exception as ex:
            warnings.warn(f'{self} read error {utils.strex(ex)}')

        finally:
            # Clear -> load from database -> merge defaults
            TwinKeyDict.clear(self)
            for obj in data:
                TwinKeyDict.__setitem__(self, obj.keys, obj.data)
            for obj in self._defaults:
                with suppress(TwinKeyError):
                    if obj.keys not in self:
                        self.__setitem__(obj.keys, obj.data)

            self._ready_event.set()

    async def write(self):
        await asyncio.wait_for(self._ready_event.wait(), READY_TIMEOUT.total_seconds())
        if self.key is None:
            raise RuntimeError('Document key not set - did read() fail?')

        data = [TwinkeyEntry(keys=k, data=v)
                for k, v in self.items()]
        content = TwinkeyEntriesBox(
            value=TwinkeyEntriesValue(
                id=self.key,
                namespace=const.SPARK_NAMESPACE,
                data=data
            )
        )
        await self._client.post('/set',
                                json=content.model_dump(mode='json'))
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
            self.__setitem__(obj.keys, obj.data)


@asynccontextmanager
async def lifespan():
    async with CV.get().lifespan():
        yield


def setup():
    CV.set(ServiceBlockStore(defaults=SYS_OBJECTS))
