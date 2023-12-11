"""
Stores persistent service-specific configuration
"""

import asyncio
import json
import logging
import warnings
from contextlib import contextmanager
from contextvars import ContextVar

from httpx import AsyncClient

from . import const, utils
from .datastore import STORE_URL, FlushedStore

SERVICE_STORE_KEY = '{name}-service-db'
READY_TIMEOUT_S = 60

# Known fields
RECONNECT_DELAY_KEY = 'reconnect_delay'
AUTOCONNECTING_KEY = 'autoconnecting'

SYS_OBJECTS = [
    {'keys': keys, 'data': {}}
    for keys in const.SYS_OBJECT_KEYS
]

LOGGER = logging.getLogger(__name__)
CV: ContextVar['ServiceConfigStore'] = ContextVar('service_store.ServiceConfigStore')


class ServiceConfigStore(FlushedStore):
    """
    Database-backed configuration
    """

    def __init__(self):
        config = utils.get_config()

        self.key = SERVICE_STORE_KEY.format(name=config.name)
        self._stored_config: dict = {}
        self._client = AsyncClient(base_url=STORE_URL)
        self._ready_event = asyncio.Event()

    def __str__(self):
        return f'<{type(self).__name__}>'

    @contextmanager
    def open(self):
        before = json.dumps(self._stored_config)
        yield self._stored_config
        after = json.dumps(self._stored_config)
        if before != after:
            self.set_changed()

    async def read(self):
        data = {}

        try:
            self._ready_event.clear()
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
            self._stored_config = data
            self._ready_event.set()

    @non_isolated
    async def write(self):
        await asyncio.wait_for(self._ready_event.wait(), READY_TIMEOUT_S)
        await http.session(self.app).post(f'{STORE_URL}/set', json={
            'value': {
                'id': self.key,
                'namespace': const.SPARK_NAMESPACE,
                'data': self._stored_config,
            },
        })
        LOGGER.info(f'{self} saved config: {self._stored_config}')


def setup(app: web.Application):
    features.add(app, ServiceConfigStore(app))


def fget(app: web.Application) -> ServiceConfigStore:
    return features.get(app, ServiceConfigStore)

# Convenience functions for know configuration


def get_autoconnecting(app: web.Application) -> bool:
    return bool(fget(app)._stored_config.get(AUTOCONNECTING_KEY, True))


def set_autoconnecting(app: web.Application, enabled: bool) -> bool:
    enabled = bool(enabled)
    with fget(app).open() as config:
        config[AUTOCONNECTING_KEY] = enabled
    return enabled


def get_reconnect_delay(app: web.Application) -> float:
    return float(fget(app)._stored_config.get(RECONNECT_DELAY_KEY, 0))


def set_reconnect_delay(app: web.Application, value: float) -> float:
    value = float(value)
    with fget(app).open() as config:
        config[RECONNECT_DELAY_KEY] = value
    return value
