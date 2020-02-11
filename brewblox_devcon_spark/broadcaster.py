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
        config = self.app['config']
        self.name = config['name']
        self.interval = config['broadcast_interval']
        self.validity = '30s'
        self.history_exchange = config['history_exchange']
        self.state_exchange = config['state_exchange']

        if self.interval <= 0 or config['volatile']:
            raise repeater.RepeaterCancelled()

        self.api = ObjectApi(self.app)
        self.publisher = events.get_publisher(self.app)

    async def run(self):
        try:
            await asyncio.sleep(self.interval)

            state_service = {
                'key': self.name,
                'type': 'Spark.service',
                'duration': self.validity,
                'data': state.summary_dict(self.app),
            }

            await self.publisher.publish(
                exchange=self.state_exchange,
                routing=self.name,
                message=state_service,
            )

            # Return early if we can't fetch blocks
            if not await state.wait_synchronize(self.app, wait=False):
                return

            state_blocks = {
                'key': self.name,
                'type': 'Spark.blocks',
                'duration': self.validity,
                'data': await self.api.all(),
            }

            await self.publisher.publish(
                exchange=self.state_exchange,
                routing=self.name,
                message=state_blocks
            )

            history_message = {
                obj[API_SID_KEY]: obj[API_DATA_KEY]
                for obj in await self.api.all_logged()
                if not obj[API_SID_KEY].startswith(GENERATED_ID_PREFIX)
            }

            # Don't broadcast history when empty
            if history_message:
                await self.publisher.publish(
                    exchange=self.history_exchange,
                    routing=self.name,
                    message=history_message
                )

        except exceptions.ConnectionPaused:
            LOGGER.debug(f'{self} interrupted: connection paused')
