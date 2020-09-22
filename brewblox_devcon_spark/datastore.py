"""
Stores service-related data associated with objects.
"""


import asyncio
import json
import warnings
from abc import abstractmethod
from contextlib import contextmanager, suppress
from functools import wraps
from typing import List

from aiohttp import web
from brewblox_service import brewblox_logger, features, http, repeater, strex

from brewblox_devcon_spark import const
from brewblox_devcon_spark.twinkeydict import TwinKeyDict, TwinKeyError

LOGGER = brewblox_logger(__name__)

STORE_URL = 'http://history:5000/history/datastore'
RETRY_INTERVAL_S = 1
FLUSH_DELAY_S = 5
READY_TIMEOUT_S = 60
SHUTDOWN_WRITE_TIMEOUT_S = 2

SYS_OBJECTS = [
    {'keys': keys, 'data': {}}
    for keys in const.SYS_OBJECT_KEYS
]

NAMESPACE = 'spark-service'
BLOCK_STORE_KEY = '{id}-blocks-db'
SERVICE_STORE_KEY = '{name}-service-db'


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
    num_attempts = 0
    while True:
        try:
            await http.session(app).get(f'{STORE_URL}/ping')
            return
        except asyncio.CancelledError:  # pragma: no cover
            raise
        except Exception as ex:
            LOGGER.error(strex(ex))
            num_attempts += 1
            if num_attempts % 10 == 0:
                LOGGER.info(f'Waiting for datastore... ({strex(ex)})')
            await asyncio.sleep(RETRY_INTERVAL_S)


class FlushedStore(repeater.RepeaterFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)
        self._volatile = app['config']['volatile']
        self._changed_event: asyncio.Event = None

    @property
    def volatile(self):
        return self._volatile

    def set_changed(self):
        if self._changed_event:
            self._changed_event.set()

    async def before_shutdown(self, app: web.Application):
        await super().before_shutdown(app)
        await self.end()
        self._changed_event = None

    async def prepare(self):
        self._changed_event = asyncio.Event()
        if self._volatile:
            LOGGER.info(f'{self} is volatile (will not read/write datastore)')
            raise repeater.RepeaterCancelled()

    async def run(self):
        try:
            await self._changed_event.wait()
            await asyncio.sleep(FLUSH_DELAY_S)
            await self.write()
            self._changed_event.clear()

        except asyncio.CancelledError:
            LOGGER.debug(f'Writing data while closing {self}')
            with suppress(Exception):
                if self._changed_event.is_set():
                    await asyncio.wait_for(self.write(), timeout=SHUTDOWN_WRITE_TIMEOUT_S)
            raise

        except Exception as ex:
            warnings.warn(f'{self} flush error {strex(ex)}')

    @abstractmethod
    async def write(self):
        """
        Must be implemented by child classes.
        FlushedStore handles how and when write() is called.
        """


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


class ServiceConfigStore(FlushedStore):
    """
    Database-backed configuration
    """

    def __init__(self, app: web.Application):
        super().__init__(app)
        self._config: dict = {}
        self._ready_event: asyncio.Event = None
        self.key: str = SERVICE_STORE_KEY.format(name=self.app['config']['name'])

    def __str__(self):
        return f'<{type(self).__name__} for {NAMESPACE}:{self.key}>'

    async def startup(self, app: web.Application):
        await FlushedStore.startup(self, app)
        self._ready_event = asyncio.Event()

    async def shutdown(self, app: web.Application):
        await FlushedStore.shutdown(self, app)
        self._ready_event = None

    @contextmanager
    def open(self):
        before = json.dumps(self._config)
        yield self._config
        after = json.dumps(self._config)
        if before != after:
            self.set_changed()

    async def read(self):
        data = {}

        try:
            self._ready_event.clear()
            if not self.volatile:
                resp = await http.session(self.app).post(f'{STORE_URL}/get', json={
                    'id': self.key,
                    'namespace': NAMESPACE,
                })
                # `value` is None if no document is found.
                resp_value = (await resp.json())['value']
                if resp_value is None:
                    warnings.warn(f'{self} found no config. Defaults will be used.')
                else:
                    data = resp_value.get('data', {})
                    LOGGER.info(f'{self} read config: {data}')

        except asyncio.CancelledError:  # pragma: no cover
            raise

        except Exception as ex:
            warnings.warn(f'{self} read error {strex(ex)}')

        finally:
            self._config = data
            self._ready_event.set()

    @non_volatile
    async def write(self):
        await asyncio.wait_for(self._ready_event.wait(), READY_TIMEOUT_S)
        await http.session(self.app).post(f'{STORE_URL}/set', json={
            'value': {
                'id': self.key,
                'namespace': NAMESPACE,
                'data': self._config,
            },
        })
        LOGGER.info(f'{self} saved config: {self._config}')


def setup(app: web.Application):
    features.add(app, ServiceBlockStore(app, defaults=SYS_OBJECTS))
    features.add(app, ServiceConfigStore(app))


def get_block_store(app: web.Application) -> ServiceBlockStore:
    return features.get(app, ServiceBlockStore)


def get_config_store(app: web.Application) -> ServiceConfigStore:
    return features.get(app, ServiceConfigStore)
