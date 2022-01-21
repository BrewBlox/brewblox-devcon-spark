"""
Intermittently broadcasts status and blocks to the eventbus
"""


import asyncio

from aiohttp import web
from brewblox_service import brewblox_logger, features, mqtt, repeater, strex

from brewblox_devcon_spark import const, controller, service_status
from brewblox_devcon_spark.block_analysis import (calculate_drive_chains,
                                                  calculate_relations)

LOGGER = brewblox_logger(__name__)


class Broadcaster(repeater.RepeaterFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)

        config = app['config']
        self.name = config['name']
        self.interval = config['broadcast_interval']
        self.volatile = self.interval <= 0 or config['volatile']
        self.state_topic = config['state_topic'] + f'/{self.name}'
        self.history_topic = config['history_topic'] + f'/{self.name}'

        self._will_message = {
            'key': self.name,
            'type': 'Spark.state',
            'data': {
                'status': None,
                'blocks': [],
            },
        }

        # A will is published if the client connection is broken
        mqtt.set_client_will(app,
                             self.state_topic,
                             self._will_message)

    async def prepare(self):
        if self.volatile:
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
            synched = await service_status.wait_synchronized(self.app, wait=False)

            status_data = service_status.desc(self.app)
            blocks = []

            try:
                if synched:
                    blocks, logged_blocks = await controller.fget(self.app).list_broadcast_blocks()

                    # Convert list to key/value format suitable for history
                    history_data = {
                        block.id: block.data
                        for block in logged_blocks
                        if not block.id.startswith(const.GENERATED_ID_PREFIX)
                    }

                    await mqtt.publish(self.app,
                                       self.history_topic,
                                       err=False,
                                       message={
                                           'key': self.name,
                                           'data': history_data,
                                       })

            finally:
                # State event is always published
                await mqtt.publish(self.app,
                                   self.state_topic,
                                   err=False,
                                   retain=True,
                                   message={
                                       'key': self.name,
                                       'type': 'Spark.state',
                                       'data': {
                                           'status': status_data.dict(),
                                           'blocks': [v.dict() for v in blocks],
                                           'relations': calculate_relations(blocks),
                                           'drive_chains': calculate_drive_chains(blocks),
                                       },
                                   })

        except Exception as ex:
            LOGGER.debug(f'{self} exception: {strex(ex)}')
            raise ex


def setup(app: web.Application):
    features.add(app, Broadcaster(app))


def fget(app: web.Application) -> Broadcaster:
    return features.get(app, Broadcaster)
