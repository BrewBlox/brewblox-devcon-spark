"""
Intermittently broadcasts controller state to the eventbus
"""


import asyncio
from time import monotonic

from aiohttp import web
from brewblox_service import brewblox_logger, features, mqtt, repeater, strex

from brewblox_devcon_spark import exceptions, state
from brewblox_devcon_spark.api.object_api import (API_DATA_KEY, API_SID_KEY,
                                                  ObjectApi)
from brewblox_devcon_spark.device import GENERATED_ID_PREFIX

LOGGER = brewblox_logger(__name__)


class Broadcaster(repeater.RepeaterFeature):

    async def prepare(self):
        config = self.app['config']
        self.name = config['name']
        self.interval = config['broadcast_interval']
        self.timeout = config['broadcast_timeout']
        self.validity = str(config['broadcast_valid']) + 's'
        self.state_topic = config['state_topic'] + f'/{self.name}'
        self.history_topic = config['history_topic'] + f'/{self.name}'

        self.blocks_topic = f'{self.state_topic}/blocks'
        self.service_topic = f'{self.state_topic}/service'

        self._synched = False
        self._last_ok = monotonic()

        if self.interval <= 0 or config['volatile']:
            raise repeater.RepeaterCancelled()

        self.api = ObjectApi(self.app)

    async def run(self):
        try:
            await asyncio.sleep(self.interval)

            state_service = {
                'key': self.name,
                'type': 'Spark.service',
                'ttl': self.validity,
                'data': state.summary_dict(self.app),
            }

            await mqtt.publish(self.app,
                               self.service_topic,
                               state_service,
                               err=False)

            # Return early if we can't fetch blocks
            self._synched = await state.wait_synchronize(self.app, wait=False)
            if not self._synched:
                self._last_ok = monotonic()
                return

            state_blocks = {
                'key': self.name,
                'type': 'Spark.blocks',
                'ttl': self.validity,
                'data': await self.api.all(),
            }

            await mqtt.publish(self.app,
                               self.blocks_topic,
                               state_blocks,
                               err=False,
                               retain=True)

            history_message = {
                'key': self.name,
                'data': {
                    obj[API_SID_KEY]: obj[API_DATA_KEY]
                    for obj in await self.api.all_logged()
                    if not obj[API_SID_KEY].startswith(GENERATED_ID_PREFIX)
                },
            }

            # Don't broadcast history when empty
            if history_message['data']:
                await mqtt.publish(self.app,
                                   self.history_topic,
                                   history_message,
                                   err=False)

            self._last_ok = monotonic()
        except exceptions.ConnectionPaused:
            LOGGER.debug(f'{self} interrupted: connection paused')

        except Exception as ex:
            LOGGER.debug(f'{self} exception: {strex(ex)}')
            if self._synched \
                    and self.timeout > 0 \
                    and self._last_ok + self.timeout < monotonic():  # pragma: no cover
                LOGGER.error('Broadcast retry attemps exhaused. Exiting now.')
                raise web.GracefulExit()
            raise


def setup(app: web.Application):
    features.add(app, Broadcaster(app))


def get_broadcaster(app: web.Application) -> Broadcaster:
    return features.get(app, Broadcaster)
