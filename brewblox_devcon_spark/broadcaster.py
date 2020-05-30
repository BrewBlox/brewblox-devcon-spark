"""
Intermittently broadcasts controller state to the eventbus
"""


import asyncio
from time import monotonic

from aiohttp import web
from brewblox_service import brewblox_logger, events, features, repeater

from brewblox_devcon_spark import exceptions, state
from brewblox_devcon_spark.api.object_api import (API_DATA_KEY, API_SID_KEY,
                                                  ObjectApi)
from brewblox_devcon_spark.device import GENERATED_ID_PREFIX

LOGGER = brewblox_logger(__name__)
EXCHANGE = 'amq.topic'


class Broadcaster(repeater.RepeaterFeature):

    async def prepare(self):
        config = self.app['config']
        self.name = config['name']
        self.interval = config['broadcast_interval']
        self.timeout = config['broadcast_timeout']
        self.validity = str(config['broadcast_valid']) + 's'
        self.history_exchange = config['history_exchange']
        self.state_topic = config['state_topic']

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

            await events.publish(self.app,
                                 exchange=EXCHANGE,
                                 routing=self.state_topic,
                                 message=state_service,
                                 exchange_declare=False)

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

            await events.publish(self.app,
                                 exchange=EXCHANGE,
                                 routing=self.state_topic,
                                 message=state_blocks,
                                 exchange_declare=False)

            history_message = {
                obj[API_SID_KEY]: obj[API_DATA_KEY]
                for obj in await self.api.all_logged()
                if not obj[API_SID_KEY].startswith(GENERATED_ID_PREFIX)
            }

            # Don't broadcast history when empty
            if history_message:
                await events.publish(self.app,
                                     exchange=self.history_exchange,
                                     routing=self.name,
                                     message=history_message)

            self._last_ok = monotonic()
        except exceptions.ConnectionPaused:
            LOGGER.debug(f'{self} interrupted: connection paused')

        except Exception:
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
