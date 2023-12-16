"""
Stores persistent service-specific configuration
"""

import asyncio
import logging
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from datetime import timedelta
from typing import Generator

from httpx import AsyncClient

from . import const, utils
from .datastore import STORE_URL, FlushedStore
from .models import (DatastoreSingleQuery, ServiceConfigBox, ServiceConfigData,
                     ServiceConfigValue)

SERVICE_STORE_KEY = '{name}-service-db'
READY_TIMEOUT = timedelta(minutes=1)


LOGGER = logging.getLogger(__name__)
CV: ContextVar['ServiceConfigStore'] = ContextVar('service_store.ServiceConfigStore')


class ServiceConfigStore(FlushedStore):
    """
    Database-backed configuration
    """

    def __init__(self):
        super().__init__()
        config = utils.get_config()

        self._key = SERVICE_STORE_KEY.format(name=config.name)
        self._data = ServiceConfigData()
        self._client = AsyncClient(base_url=STORE_URL)
        self._ready_ev = asyncio.Event()

    def __str__(self):
        return f'<{type(self).__name__}>'

    @contextmanager
    def open(self) -> Generator[ServiceConfigData, None, None]:
        copy = self._data.model_copy()
        self._data.model_config
        yield copy
        if copy != self._data:
            self._data = copy
            self.set_changed()

    async def read(self):
        try:
            self._ready_ev.clear()
            query = DatastoreSingleQuery(
                id=self._key,
                namespace=const.SPARK_NAMESPACE
            )
            resp = await self._client.post('/get', json=query.model_dump(mode='json'))
            box = ServiceConfigBox.model_validate_json(resp.text)
            if box.value:
                LOGGER.info(f'{self} read {box.value}')
                self._data = box.value.data
            else:
                LOGGER.warn(f'{self} found no config. Defaults will be used.')
                self._data = ServiceConfigData()

        except Exception as ex:
            LOGGER.warn(f'{self} read error {utils.strex(ex)}')

        finally:
            self._ready_ev.set()

    async def write(self):
        await asyncio.wait_for(self._ready_ev.wait(), READY_TIMEOUT.total_seconds())
        box = ServiceConfigBox(
            value=ServiceConfigValue(
                id=self._key,
                namespace=const.SPARK_NAMESPACE,
                data=self._data,
            ))
        await self._client.post('/set', json=box.model_dump(mode='json'))
        LOGGER.info(f'{self} saved config: {self._data}')


@asynccontextmanager
async def lifespan():
    async with CV.get().lifespan():
        yield


def setup():
    CV.set(ServiceConfigStore())
