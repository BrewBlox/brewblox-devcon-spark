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
from brewblox_devcon_spark.datastore import (STORE_URL, FlushedStore,
                                             non_isolated)

SERVICE_STORE_KEY = '{name}-service-db'
READY_TIMEOUT_S = 60

# Known fields
RECONNECT_INTERVAL_KEY = 'reconnect_interval'
AUTOCONNECTING_KEY = 'autoconnecting'

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
        return f'<{type(self).__name__}>'

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
            if not self.isolated:
                resp = await http.session(self.app).post(f'{STORE_URL}/get', json={
                    'id': self.key,
                    'namespace': const.SPARK_NAMESPACE,
                })
                # `value` is None if no document is found.
                resp_value = (await resp.json())['value']
                if resp_value:
                    LOGGER.info(f'{self} read {resp_value}')
                    data = resp_value.get('data', {})
                else:
                    warnings.warn(f'{self} found no config. Defaults will be used.')

        except Exception as ex:
            warnings.warn(f'{self} read error {strex(ex)}')

        finally:
            self._config = data
            self._ready_event.set()

    @non_isolated
    async def write(self):
        await asyncio.wait_for(self._ready_event.wait(), READY_TIMEOUT_S)
        await http.session(self.app).post(f'{STORE_URL}/set', json={
            'value': {
                'id': self.key,
                'namespace': const.SPARK_NAMESPACE,
                'data': self._config,
            },
        })
        LOGGER.info(f'{self} saved config: {self._config}')


def setup(app: web.Application):
    features.add(app, ServiceConfigStore(app))


def fget(app: web.Application) -> ServiceConfigStore:
    return features.get(app, ServiceConfigStore)

# Convenience functions for know configuration


def get_autoconnecting(app: web.Application) -> bool:
    return bool(fget(app)._config.get(AUTOCONNECTING_KEY, True))


def set_autoconnecting(app: web.Application, enabled: bool) -> bool:
    enabled = bool(enabled)
    with fget(app).open() as config:
        config[AUTOCONNECTING_KEY] = enabled
    return enabled


def get_reconnect_interval(app: web.Application) -> float:
    return float(fget(app)._config.get(RECONNECT_INTERVAL_KEY, 0))


def set_reconnect_interval(app: web.Application, interval: float) -> float:
    interval = float(interval)
    with fget(app).open() as config:
        config[RECONNECT_INTERVAL_KEY] = interval
    return interval
