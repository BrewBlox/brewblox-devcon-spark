"""
Intermittently broadcasts controller state to the eventbus
"""


import asyncio

from aiohttp import web
from brewblox_service import brewblox_logger, events, features, repeater

from brewblox_devcon_spark import exceptions, state
from brewblox_devcon_spark.api.object_api import (API_DATA_KEY, API_SID_KEY,
                                                  ObjectApi)
from brewblox_devcon_spark.device import GENERATED_ID_PREFIX

LOGGER = brewblox_logger(__name__)


def get_broadcaster(app: web.Application):
    return features.get(app, Broadcaster)


def setup(app: web.Application):
    features.add(app, Broadcaster(app))


class Broadcaster(repeater.RepeaterFeature):

    async def prepare(self):
        self.name = self.app['config']['name']
        self.interval = self.app['config']['broadcast_interval']
        self.exchange = self.app['config']['broadcast_exchange']

        if self.interval <= 0 or self.app['config']['volatile']:
            raise repeater.RepeaterCancelled()

        self.api = ObjectApi(self.app)
        self.publisher = events.get_publisher(self.app)

    async def run(self):
        try:
            await state.wait_synchronize(self.app)
            await asyncio.sleep(self.interval)
            current_objects = {
                obj[API_SID_KEY]: obj[API_DATA_KEY]
                for obj in await self.api.all_logged()
                if not obj[API_SID_KEY].startswith(GENERATED_ID_PREFIX)
            }

            # Don't broadcast when empty
            if not current_objects:
                return

            await self.publisher.publish(
                exchange=self.exchange,
                routing=self.name,
                message=current_objects
            )

        except exceptions.ConnectionPaused:
            LOGGER.debug(f'{self} interrupted: connection paused')
