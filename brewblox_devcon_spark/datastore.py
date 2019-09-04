"""
Stores service-related data associated with objects.
"""


import asyncio
import json
import warnings
from abc import abstractmethod
from contextlib import contextmanager, suppress
from functools import wraps
from typing import Any, Callable, List

from aiohttp import web
from brewblox_service import (brewblox_logger, couchdb_client, features,
                              scheduler, strex)

from brewblox_devcon_spark.twinkeydict import TwinKeyDict, TwinKeyError

LOGGER = brewblox_logger(__name__)

GROUPS_NID = 1
SYSINFO_NID = 2
SYSTIME_NID = 3
ONEWIREBUS_NID = 4
WIFI_SETTINGS_NID = 5
TOUCH_SETTINGS_NID = 6
DISPLAY_SETTINGS_NID = 7
SPARK_PINS_NID = 19


FLUSH_DELAY_S = 5
DB_NAME = 'spark-service'
OBJECT_NID_START = 100
SYS_OBJECT_KEYS = [
    ['ActiveGroups', GROUPS_NID],
    ['SystemInfo', SYSINFO_NID],
    ['SystemTime', SYSTIME_NID],
    ['OneWireBus', ONEWIREBUS_NID],
    ['WiFiSettings', WIFI_SETTINGS_NID],
    ['TouchSettings', TOUCH_SETTINGS_NID],
    ['DisplaySettings', DISPLAY_SETTINGS_NID],
    ['SparkPins', SPARK_PINS_NID],
]
SYS_OBJECTS = [
    {'keys': keys, 'data': {}}
    for keys in SYS_OBJECT_KEYS
]


def setup(app: web.Application):
    features.add(app, CouchDBBlockStore(app, defaults=SYS_OBJECTS))
    features.add(app, CouchDBConfig(app), key='config')


def get_datastore(app: web.Application) -> TwinKeyDict:
    return features.get(app, CouchDBBlockStore)


def get_config(app: web.Application) -> 'CouchDBConfig':
    return features.get(app, key='config')


def non_volatile(func):
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        if self.volatile:
            return
        return await func(self, *args, **kwargs)
    return wrapper


async def check_remote(app: web.Application):
    if app['config']['volatile']:
        return
    await couchdb_client.get_client(app).check_remote()


class FlushedStore(features.ServiceFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)
        self._volatile = app['config']['volatile']

        self._flush_task: asyncio.Task = None
        self._changed_event: asyncio.Event = None

        self._document: str = None
        self._rev: str = None

    def __str__(self):
        return f'<{type(self).__name__} for {DB_NAME}/{self._document}>'

    @property
    def active(self):
        return self._flush_task and not self._flush_task.done()

    @property
    def volatile(self):
        return self._volatile

    @property
    def document(self):
        return self._document

    @document.setter
    def document(self, val):
        self._document = val

    @property
    def rev(self):
        return self._rev

    @rev.setter
    def rev(self, val):
        self._rev = val

    def set_changed(self):
        if self._changed_event:
            self._changed_event.set()

    async def startup(self, app: web.Application):
        await self.shutdown(app)
        if self._volatile:
            LOGGER.info(f'{self} is volatile (will not read/write datastore)')
            return

        self._flush_task = await scheduler.create_task(app, self._autoflush())
        self._changed_event = asyncio.Event()

    async def before_shutdown(self, app: web.Application):
        await self.shutdown(app)

    async def shutdown(self, app: web.Application):
        await scheduler.cancel_task(app, self._flush_task)
        self._flush_task = None
        self._changed_event = None

    @abstractmethod
    async def write():
        pass  # pragma: no cover

    async def _autoflush(self):
        while True:
            try:
                await self._changed_event.wait()
                await asyncio.sleep(FLUSH_DELAY_S)
                await self.write()
                self._changed_event.clear()

            except asyncio.CancelledError:
                if self._changed_event.is_set():
                    await self.write()
                break

            except Exception as ex:
                warnings.warn(f'{self} flush error {strex(ex)}')


class CouchDBBlockStore(FlushedStore, TwinKeyDict):
    """
    TwinKeyDict subclass to periodically flush contained objects to CouchDB.
    """

    def __init__(self, app: web.Application, defaults: List[dict] = None):
        FlushedStore.__init__(self, app)
        TwinKeyDict.__init__(self)
        self._defaults = defaults or []
        self._ready_event: asyncio.Event = None
        self.clear()  # inserts defaults

    async def startup(self, app: web.Application):
        await FlushedStore.startup(self, app)
        self._ready_event = asyncio.Event()

    async def shutdown(self, app: web.Application):
        await FlushedStore.shutdown(self, app)
        self._ready_event = None

    async def read(self, document: str):
        data = []

        try:
            self.rev = None
            self.document = None
            self._ready_event.clear()
            if not self.volatile:
                client = couchdb_client.get_client(self.app)
                self.rev, data = await client.read(DB_NAME, document, [])
                self.document = document
                LOGGER.info(f'{self} Read {len(data)} blocks. Rev = {self.rev}')

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
        await self._ready_event.wait()
        if self.rev is None or self.document is None:
            raise RuntimeError('Document or revision unknown - did read() fail?')
        data = [
            {'keys': keys, 'data': content}
            for keys, content in self.items()
        ]
        client = couchdb_client.get_client(self.app)
        self.rev = await client.write(DB_NAME, self.document, self.rev, data)
        LOGGER.info(f'{self} Saved {len(data)} block(s). Rev = {self.rev}')

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


class CouchDBConfig(FlushedStore):
    """
    Database-backed configuration
    """

    def __init__(self, app: web.Application):
        FlushedStore.__init__(self, app)
        self._config: dict = {}
        self._listeners = set()
        self._ready_event: asyncio.Event = None

    async def startup(self, app: web.Application):
        await FlushedStore.startup(self, app)
        self._ready_event = asyncio.Event()

    async def shutdown(self, app: web.Application):
        await FlushedStore.shutdown(self, app)
        self._ready_event = None

    def subscribe(self, func: Callable[[dict], Any]):
        self._listeners.add(func)

    @contextmanager
    def open(self):
        before = json.dumps(self._config)
        yield self._config
        after = json.dumps(self._config)
        if before != after:
            self.set_changed()

    async def read(self, document: str):
        data = {}

        try:
            self.rev = None
            self.document = None
            self._ready_event.clear()
            if not self.volatile:
                client = couchdb_client.get_client(self.app)
                self.rev, data = await client.read(DB_NAME, document, {})
                self.document = document
                LOGGER.info(f'{self} Read {len(data)} setting(s). Rev = {self.rev}')

        except asyncio.CancelledError:  # pragma: no cover
            raise

        except Exception as ex:
            warnings.warn(f'{self} read error {strex(ex)}')

        finally:
            self._config = data
            with self.open() as cfg:
                for func in self._listeners:
                    func(cfg)

            self._ready_event.set()

    @non_volatile
    async def write(self):
        await self._ready_event.wait()
        if self.rev is None or self.document is None:
            raise RuntimeError('Document or revision unknown - did read() fail?')
        client = couchdb_client.get_client(self.app)
        self.rev = await client.write(DB_NAME, self.document, self.rev, self._config)
        LOGGER.info(f'{self} Saved {len(self._config)} settings. Rev = {self.rev}')
