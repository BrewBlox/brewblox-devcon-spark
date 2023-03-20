"""
Intermittently broadcasts status and blocks to the eventbus
"""


import asyncio
import json

from aiohttp import web
from brewblox_service import brewblox_logger, features, mqtt, repeater, strex

from brewblox_devcon_spark import const, controller, service_status
from brewblox_devcon_spark.block_analysis import (calculate_claims,
                                                  calculate_relations)
from brewblox_devcon_spark.models import ServiceConfig

LOGGER = brewblox_logger(__name__)


class Broadcaster(repeater.RepeaterFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)

        config: ServiceConfig = app['config']
        self.name = config['name']
        self.interval = config['broadcast_interval']
        self.isolated = self.interval <= 0 or config['isolated']
        self.state_topic = config['state_topic'] + f'/{self.name}'
        self.history_topic = config['history_topic'] + f'/{self.name}'

        self._will_message = json.dumps({
            'key': self.name,
            'type': 'Spark.state',
            'data': None,
        })

        # A will is published if the client connection is broken
        mqtt.set_client_will(app,
                             self.state_topic,
                             self._will_message)

    async def prepare(self):
        if self.isolated:
            raise repeater.RepeaterCancelled()

    async def before_shutdown(self, app: web.Application):
        await self.end()
        # This is an orderly shutdown - MQTT will won't be published
        await mqtt.publish(self.app,
                           self.state_topic,
                           err=False,
                           retain=True,
                           message=self._will_message)

    async def run(self):
        try:
            await asyncio.sleep(self.interval)
            blocks = []

            try:
                if service_status.is_synchronized(self.app):
                    blocks, logged_blocks = await controller.fget(self.app).read_all_broadcast_blocks()

                    # Convert list to key/value format suitable for history
                    history_data = {
                        block.id: block.data
                        for block in logged_blocks
                        if not block.id.startswith(const.GENERATED_ID_PREFIX)
                    }

                    await mqtt.publish(self.app,
                                       self.history_topic,
                                       err=False,
                                       message=json.dumps({
                                           'key': self.name,
                                           'data': history_data,
                                       }))

            finally:
                # State event is always published
                await mqtt.publish(self.app,
                                   self.state_topic,
                                   err=False,
                                   retain=True,
                                   message=json.dumps({
                                       'key': self.name,
                                       'type': 'Spark.state',
                                       'data': {
                                           'status': service_status.desc(self.app).dict(),
                                           'blocks': [v.dict() for v in blocks],
                                           'relations': calculate_relations(blocks),
                                           'claims': calculate_claims(blocks),
                                       },
                                   }))

        except Exception as ex:
            LOGGER.debug(f'{self} exception: {strex(ex)}')
            raise ex


def setup(app: web.Application):
    features.add(app, Broadcaster(app))


def fget(app: web.Application) -> Broadcaster:
    return features.get(app, Broadcaster)
