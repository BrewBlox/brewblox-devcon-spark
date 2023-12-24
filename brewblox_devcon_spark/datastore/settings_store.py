import asyncio
import logging
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import timedelta
from typing import Awaitable, Callable

from httpx import AsyncClient

from .. import const, mqtt, utils
from ..models import (DatastoreEvent, DatastoreSingleQuery,
                      DatastoreSingleValueBox, StoredServiceSettingsBox,
                      StoredServiceSettingsValue, StoredTimezoneSettingsBox,
                      StoredTimezoneSettingsValue, StoredUnitSettingsBox,
                      StoredUnitSettingsValue)

Callback_ = Callable[[], Awaitable]

FETCH_TIMEOUT = timedelta(minutes=5)

LOGGER = logging.getLogger(__name__)

CV: ContextVar['SettingsStore'] = ContextVar('settings_store.SettingsStore')


class SettingsStore:

    def __init__(self) -> None:
        config = utils.get_config()
        self._ready_ev = asyncio.Event()
        self._client = AsyncClient(base_url=config.datastore_url)
        self._name = config.name

        self._service_settings = StoredServiceSettingsValue(id=config.name)
        self._unit_settings = StoredUnitSettingsValue()
        self._timezone_settings = StoredTimezoneSettingsValue()

        self._service_listeners: set[Callback_] = set()
        self._global_listeners: set[Callback_] = set()

    async def _get_box(self,
                       query: DatastoreSingleQuery,
                       model: type[DatastoreSingleValueBox]) -> DatastoreSingleValueBox:
        content = query.model_dump(mode='json')
        resp = await utils.httpx_retry(lambda: self._client.post('/get', json=content))
        box = model.model_validate_json(resp.text)
        return box

    async def _set_box(self,
                       box: DatastoreSingleValueBox):
        await self._client.post('/set', json=box.model_dump(mode='json'))

    async def fetch_all(self):
        config = utils.get_config()

        async with asyncio.timeout(FETCH_TIMEOUT.total_seconds()):
            # Fetch service settings
            box = await self._get_box(
                query=DatastoreSingleQuery(id=self._name,
                                           namespace=const.SERVICE_NAMESPACE),
                model=StoredServiceSettingsBox)
            self._service_settings = box.value or StoredServiceSettingsValue(id=config.name)

            # Fetch unit settings
            box = await self._get_box(
                query=DatastoreSingleQuery(id=const.GLOBAL_UNITS_ID,
                                           namespace=const.GLOBAL_NAMESPACE),
                model=StoredUnitSettingsBox)
            self._unit_settings = box.value or StoredUnitSettingsValue()

            # Fetch timezone settings
            box = await self._get_box(
                query=DatastoreSingleQuery(id=const.GLOBAL_TIME_ZONE_ID,
                                           namespace=const.GLOBAL_NAMESPACE),
                model=StoredUnitSettingsBox)
            self._timezone_settings = box.value or StoredTimezoneSettingsValue()

    async def on_service_store_event(self, evt: DatastoreEvent):
        dirty = False

        for value in evt.changed:
            if value.id == self._name:
                settings = StoredServiceSettingsValue.model_validate(value.model_dump())
                dirty = dirty or settings != self._service_settings
                self._service_settings = settings

        if dirty:
            for cb in set(self._service_listeners):
                await cb()

    async def on_global_store_event(self, evt: DatastoreEvent):
        dirty = False

        for value in evt.changed:
            if value.id == const.GLOBAL_UNITS_ID:
                settings = StoredUnitSettingsValue.model_validate(value.model_dump())
                dirty = dirty or settings != self._unit_settings
                self._unit_settings = settings

            if value.id == const.GLOBAL_TIME_ZONE_ID:
                settings = StoredTimezoneSettingsValue.model_validate(value.model_dump())
                dirty = dirty or settings != self._timezone_settings
                self._timezone_settings = settings

        if dirty:
            for cb in set(self._global_listeners):
                await cb()

    @property
    def service_settings_listeners(self) -> set[Callback_]:
        return self._service_listeners

    @property
    def global_settings_listeners(self) -> set[Callback_]:
        return self._global_listeners

    @property
    def service_settings(self) -> StoredServiceSettingsValue:
        return self._service_settings

    @property
    def unit_settings(self) -> StoredUnitSettingsValue:
        return self._unit_settings

    @property
    def timezone_settings(self) -> StoredTimezoneSettingsValue:
        return self._timezone_settings

    async def commit_service_settings(self):
        await self._set_box(StoredServiceSettingsBox(value=self._service_settings))


@asynccontextmanager
async def lifespan():
    await CV.get().fetch_all()
    yield


def setup():
    store = SettingsStore()
    config = utils.get_config()
    mqtt_client = mqtt.CV.get()
    CV.set(store)

    @mqtt_client.subscribe(f'{config.datastore_topic}/{const.GLOBAL_NAMESPACE}')
    async def on_global_change(client, topic, payload, qos, properties):
        await CV.get().on_global_store_event(DatastoreEvent.model_validate_json(payload))

    @mqtt_client.subscribe(f'{config.datastore_topic}/{const.SERVICE_NAMESPACE}')
    async def on_service_change(client, topic, payload, qos, properties):
        await CV.get().on_service_store_event(DatastoreEvent.model_validate_json(payload))
