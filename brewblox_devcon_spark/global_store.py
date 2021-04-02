"""
Keeps track of global config
"""

import asyncio

from aiohttp import web
from brewblox_service import brewblox_logger, features, http, mqtt, strex

from brewblox_devcon_spark import const
from brewblox_devcon_spark.datastore import STORE_URL

LOGGER = brewblox_logger(__name__)


def default_units():
    return {
        'temperature': 'degC',
    }


class GlobalConfigStore(features.ServiceFeature):
    def __init__(self, app: web.Application):
        super().__init__(app)
        self._volatile = app['config']['volatile']
        self._datastore_topic = app['config']['datastore_topic']
        self._global_topic = f'{self._datastore_topic}/{const.GLOBAL_NAMESPACE}'

        self.units = default_units()
        self.listeners = set()

    async def startup(self, app: web.Application):
        if not self._volatile:
            await mqtt.listen(app, self._global_topic, self._on_event)
            await mqtt.subscribe(app, self._global_topic)

    async def before_shutdown(self, app: web.Application):
        self.listeners.clear()

    async def shutdown(self, app: web.Application):
        if not self._volatile:
            await mqtt.unlisten(app, self._global_topic, self._on_event)
            await mqtt.unsubscribe(app, self._global_topic)

    async def _on_event(self, topic: str, obj: dict):
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

        return changed

    async def read(self):
        if self._volatile:
            return

        try:
            resp = await http.session(self.app).post(f'{STORE_URL}/mget', json={
                'namespace': const.GLOBAL_NAMESPACE,
                'ids': [const.GLOBAL_UNITS_ID],
            })
            self.update((await resp.json())['values'])

        except asyncio.CancelledError:  # pragma: no cover
            raise

        except Exception as ex:
            LOGGER.error(f'{self} read error {strex(ex)}')


def setup(app: web.Application):
    features.add(app, GlobalConfigStore(app))


def fget(app: web.Application) -> GlobalConfigStore:
    return features.get(app, GlobalConfigStore)
