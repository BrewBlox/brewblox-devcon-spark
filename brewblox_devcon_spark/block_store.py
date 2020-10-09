"""
Stores sid/nid relations for blocks
"""

import asyncio
import warnings
from contextlib import suppress
from typing import List

from aiohttp import web
from brewblox_service import brewblox_logger, features, http, strex

from brewblox_devcon_spark import const
from brewblox_devcon_spark.datastore import (NAMESPACE, STORE_URL,
                                             FlushedStore, non_volatile)
from brewblox_devcon_spark.twinkeydict import TwinKeyDict, TwinKeyError

BLOCK_STORE_KEY = '{id}-blocks-db'
READY_TIMEOUT_S = 60

SYS_OBJECTS = [
    {'keys': keys, 'data': {}}
    for keys in const.SYS_OBJECT_KEYS
]

LOGGER = brewblox_logger(__name__)


class ServiceBlockStore(FlushedStore, TwinKeyDict):
    """
    TwinKeyDict subclass to periodically flush contained objects to Redis.
    """

    def __init__(self, app: web.Application, defaults: List[dict]):
        FlushedStore.__init__(self, app)
        TwinKeyDict.__init__(self)

        self.key: str = None
        self._defaults = defaults
        self._ready_event: asyncio.Event = None

        self.clear()  # inserts defaults

    def __str__(self):
        return f'<{type(self).__name__} for {NAMESPACE}:{self.key}>'

    async def startup(self, app: web.Application):
        await FlushedStore.startup(self, app)
        self._ready_event = asyncio.Event()

    async def shutdown(self, app: web.Application):
        await FlushedStore.shutdown(self, app)
        self._ready_event = None

    async def read(self, device_id: str):
        key = BLOCK_STORE_KEY.format(id=device_id)
        data = []

        try:
            self.key = None
            self._ready_event.clear()
            if not self.volatile:
                resp = await http.session(self.app).post(f'{STORE_URL}/get', json={
                    'id': key,
                    'namespace': NAMESPACE,
                })
                self.key = key
                data = (await resp.json())['value'].get('data', [])
                LOGGER.info(f'{self} Read {len(data)} blocks')

        except asyncio.CancelledError:  # pragma: no cover
            raise

        except Exception as ex:
            warnings.warn(f'{self} read error {strex(ex)}')

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

    @non_volatile
    async def write(self):
        await asyncio.wait_for(self._ready_event.wait(), READY_TIMEOUT_S)
        if self.key is None:
            raise RuntimeError('Document key not set - did read() fail?')
        data = [
            {'keys': keys, 'data': content}
            for keys, content in self.items()
        ]
        await http.session(self.app).post(f'{STORE_URL}/set', json={
            'value': {
                'id': self.key,
                'namespace': NAMESPACE,
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


def setup(app: web.Application):
    features.add(app, ServiceBlockStore(app, defaults=SYS_OBJECTS))


def fget(app: web.Application) -> ServiceBlockStore:
    return features.get(app, ServiceBlockStore)
