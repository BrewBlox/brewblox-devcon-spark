"""
Stores service-related data associated with objects.
"""


import asyncio
import json
import warnings
from contextlib import contextmanager, suppress
from typing import List

from aiohttp import web
from brewblox_service import brewblox_logger, features, scheduler

from brewblox_devcon_spark import couchdb_client
from brewblox_devcon_spark.twinkeydict import TwinKeyDict, TwinKeyError

LOGGER = brewblox_logger(__name__)

PROFILES_CONTROLLER_ID = 1
SYSINFO_CONTROLLER_ID = 2
TIME_CONTROLLER_ID = 3
ONEWIREBUS_CONTROLLER_ID = 4


FLUSH_DELAY_S = 5
DB_NAME = 'spark-service'
OBJECT_ID_START = 100
SYS_OBJECTS = [
    {'keys': keys, 'data': {}}
    for keys in [
        ['__profiles', PROFILES_CONTROLLER_ID],
        ['__sysinfo', SYSINFO_CONTROLLER_ID],
        ['__time', TIME_CONTROLLER_ID],
        ['__onewirebus', ONEWIREBUS_CONTROLLER_ID],
        # Spark V3
        ['__pin_bottom_1', 10],
        ['__pin_bottom_2', 11],
        ['__pin_top_1', 12],
        ['__pin_top_2', 13],
        ['__pin_top_3', 14],
        # Spark V1/V2
        ['__actuator_0', 15],
        ['__actuator_1', 16],
        ['__actuator_2', 17],
        ['__actuator_3', 18],
    ]
]


def setup(app: web.Application):
    features.add(app, CouchDBBlockStore(app, defaults=SYS_OBJECTS))
    features.add(app, CouchDBConfig(app))


def get_datastore(app: web.Application) -> TwinKeyDict:
    return features.get(app, CouchDBBlockStore)


def get_config(app: web.Application) -> 'CouchDBConfig':
    return features.get(app, CouchDBConfig)


class CouchDBBlockStore(features.ServiceFeature, TwinKeyDict):
    """
    TwinKeyDict subclass to periodically flush contained objects to CouchDB.
    """

    def __init__(self,
                 app: web.Application,
                 defaults: List[dict] = None,  # key: tuple, data: any
                 ):
        features.ServiceFeature.__init__(self, app)
        TwinKeyDict.__init__(self)

        self._client: couchdb_client.CouchDBClient = None
        self._flush_task: asyncio.Task = None
        self._changed_event: asyncio.Event = None
        self._ready_event: asyncio.Event = None

        self._volatile = app['config']['volatile']
        self._defaults = defaults or []
        self._doc_name = None
        self._rev = None

    def __str__(self):
        return f'<{type(self).__name__} for {DB_NAME}/{self._doc_name}>'

    @property
    def active(self):
        return self._flush_task and not self._flush_task.done()

    async def startup(self, app: web.Application):
        await self.shutdown(app)
        if self._volatile:
            self.clear()
            LOGGER.info(f'{self} is volatile (will not read/write datastore)')
            return

        self._flush_task = await scheduler.create_task(app, self._autoflush())
        self._client = couchdb_client.get_client(app)
        self._changed_event = asyncio.Event()
        self._ready_event = asyncio.Event()

    async def shutdown(self, app: web.Application):
        await scheduler.cancel_task(app, self._flush_task)
        self._flush_task = None
        self._client = None
        self._changed_event = None
        self._ready_event = None

    async def read(self, document: str):
        if self._volatile:
            return

        self._ready_event.clear()

        try:
            self._rev, data = await self._client.read(DB_NAME, document, [])
            self._doc_name = document
            LOGGER.info(f'{self} Read {len(data)} blocks. Rev = {self._rev}')

            for obj in data:
                TwinKeyDict.__setitem__(self, obj['keys'], obj['data'])

            for obj in self._defaults:
                with suppress(TwinKeyError):
                    if obj['keys'] not in self:
                        self.__setitem__(obj['keys'], obj['data'])

        finally:
            self._ready_event.set()

    async def write(self):
        if self._volatile:
            return

        await self._ready_event.wait()
        data = [
            {'keys': keys, 'data': content}
            for keys, content in self.items()
        ]
        self._rev = await self._client.write(DB_NAME, self._doc_name, self._rev, data)
        LOGGER.info(f'{self} Saved {len(data)} blocks. Rev = {self._rev}')

    async def _autoflush(self):
        while True:
            try:
                await self._changed_event.wait()
                await asyncio.sleep(FLUSH_DELAY_S)
                await self.write()
                self._changed_event.clear()

            except asyncio.CancelledError:
                await self.write()
                break

            except Exception as ex:
                warnings.warn(f'{self} {type(ex).__name__}({ex})')

    def __setitem__(self, keys, item):
        TwinKeyDict.__setitem__(self, keys, item)
        if self._changed_event:
            self._changed_event.set()

    def __delitem__(self, keys):
        TwinKeyDict.__delitem__(self, keys)
        if self._changed_event:
            self._changed_event.set()

    def clear(self):
        TwinKeyDict.clear(self)
        for obj in self._defaults:
            self.__setitem__(obj['keys'], obj['data'])


class CouchDBConfig(features.ServiceFeature):
    """
    Database-backed configuration
    """

    def __init__(self, app: web.Application):
        features.ServiceFeature.__init__(self, app)
        self._volatile = app['config']['volatile']
        self._config: dict = {}
        self._doc_name = None
        self._rev = None
        self._client: couchdb_client.CouchDBClient = None
        self._flush_task: asyncio.Task = None
        self._changed_event: asyncio.Event = None
        self._ready_event: asyncio.Event = None

    def __str__(self):
        return f'<{type(self).__name__} for {DB_NAME}/{self._doc_name}>'

    @property
    def active(self):
        return self._flush_task and not self._flush_task.done()

    async def startup(self, app: web.Application):
        await self.shutdown(app)
        if self._volatile:
            LOGGER.info(f'{self} is volatile (will not read/write datastore)')
            return

        self._flush_task = await scheduler.create_task(app, self._autoflush())
        self._client = couchdb_client.get_client(app)
        self._changed_event = asyncio.Event()
        self._ready_event = asyncio.Event()

    async def shutdown(self, app: web.Application):
        await scheduler.cancel_task(app, self._flush_task)
        self._flush_task = None
        self._client = None
        self._changed_event = None
        self._ready_event = None

    @contextmanager
    def open(self):
        before = json.dumps(self._config)
        yield self._config
        after = json.dumps(self._config)
        if before != after and self._changed_event:
            self._changed_event.set()

    async def read(self, document: str):
        if self._volatile:
            return

        self._ready_event.clear()

        try:
            self._rev, self._config = await self._client.read(DB_NAME, document, {})
            self._doc_name = document
            LOGGER.info(f'{self} Read {len(self._config)} settings. Rev = {self._rev}')

        finally:
            self._ready_event.set()

    async def write(self):
        if self._volatile:
            return

        await self._ready_event.wait()
        self._rev = await self._client.write(DB_NAME, self._doc_name, self._rev, self._config)
        LOGGER.info(f'{self} Saved {len(self._config)} settings. Rev = {self._rev}')

    async def _autoflush(self):
        while True:
            try:
                await self._changed_event.wait()
                await asyncio.sleep(FLUSH_DELAY_S)
                await self.write()
                self._changed_event.clear()

            except asyncio.CancelledError:
                await self.write()
                break

            except Exception as ex:
                warnings.warn(f'{self} {type(ex).__name__}({ex})')
