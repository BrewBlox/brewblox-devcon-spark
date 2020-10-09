"""
Stores persistent service-specific configuration
"""

import asyncio
import json
import warnings
from contextlib import contextmanager

from aiohttp import web
from brewblox_service import brewblox_logger, features, http, strex

from brewblox_devcon_spark import const
from brewblox_devcon_spark.datastore import (NAMESPACE, STORE_URL,
                                             FlushedStore, non_volatile)

SERVICE_STORE_KEY = '{name}-service-db'
READY_TIMEOUT_S = 60

SYS_OBJECTS = [
    {'keys': keys, 'data': {}}
    for keys in const.SYS_OBJECT_KEYS
]

LOGGER = brewblox_logger(__name__)


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
    features.add(app, ServiceConfigStore(app))


def fget(app: web.Application) -> ServiceConfigStore:
    return features.get(app, ServiceConfigStore)
