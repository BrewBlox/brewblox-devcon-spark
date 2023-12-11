"""
Keeps track of global config
"""

import json
import logging
from contextlib import asynccontextmanager
from contextvars import ContextVar

from httpx import AsyncClient

from . import const, mqtt, utils
from .datastore import STORE_URL
from .models import DatastoreMultiQuery, DatastoreMultiValueBox

LOGGER = logging.getLogger(__name__)
CV: ContextVar['GlobalConfigStore'] = ContextVar('global_store.GlobalConfigStore')


def default_units():
    return {
        'temperature': 'degC',
    }


def default_time_zone():
    return {
        'name': 'Etc/UTC',
        'posixValue': 'UTC0',
    }


class GlobalConfigStore:
    def __init__(self):
        self._client = AsyncClient(base_url=STORE_URL)

        self.units = default_units()
        self.time_zone = default_time_zone()
        self.listeners = set()

    async def on_event(self, obj: dict):
        if self.update(obj.get('changed', [])):
            for cb in set(self.listeners):
                await cb()

    def update(self, values: list) -> bool:
        changed = False
        for value in values:
            if value['id'] == const.GLOBAL_UNITS_ID:
                units = {'temperature': value['temperature']}
                changed = changed or units != self.units
                self.units = units
            if value['id'] == const.GLOBAL_TIME_ZONE_ID:
                tz = {
                    'name': value['name'],
                    'posixValue': value['posixValue']
                }
                changed = changed or tz != self.time_zone
                self.time_zone = tz

        return changed

    async def read(self):
        try:
            query = DatastoreMultiQuery(
                namespace=const.GLOBAL_NAMESPACE,
                ids=[
                    const.GLOBAL_UNITS_ID,
                    const.GLOBAL_TIME_ZONE_ID,
                ],
            )
            resp = await self._client.post('/mget',
                                           json=query.model_dump(mode='json'))
            resp_content = DatastoreMultiValueBox.model_validate_json(resp.text)
            self.update(resp_content.values)

        except Exception as ex:
            LOGGER.error(f'{self} read error {utils.strex(ex)}')


@asynccontextmanager
async def lifespan():
    yield
    CV.get().listeners.clear()


def setup():
    config = utils.get_config()
    mqtt_client = mqtt.CV.get()
    CV.set(GlobalConfigStore())

    @mqtt_client.subscribe(f'{config.datastore_topic}/{const.GLOBAL_NAMESPACE}')
    async def on_datastore_message(client, topic, payload, qos, properties):
        CV.get().on_event(json.loads(payload))
