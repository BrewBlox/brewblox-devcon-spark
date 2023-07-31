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
        self.name = config.name
        self.interval = config.broadcast_interval
        self.isolated = self.interval <= 0 or config.isolated
        self.state_topic = f'{config.state_topic}/{config.name}'
        self.history_topic = f'{config.history_topic}/{config.name}'

    async def prepare(self):
        if self.isolated:
            raise repeater.RepeaterCancelled()

    async def before_shutdown(self, app: web.Application):
        await self.end()

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
                                       topic=self.history_topic,
                                       payload=json.dumps({
                                           'key': self.name,
                                           'data': history_data,
                                       }),
                                       err=False,
                                       )

            finally:
                # State event is always published
                await mqtt.publish(self.app,
                                   topic=self.state_topic,
                                   payload=json.dumps({
                                       'key': self.name,
                                       'type': 'Spark.state',
                                       'data': {
                                           'status': service_status.desc(self.app).dict(),
                                           'blocks': [v.dict() for v in blocks],
                                           'relations': calculate_relations(blocks),
                                           'claims': calculate_claims(blocks),
                                       },
                                   }),
                                   retain=True,
                                   err=False,
                                   )

        except Exception as ex:
            LOGGER.debug(f'{self} exception: {strex(ex)}')
            raise ex


def setup(app: web.Application):
    features.add(app, Broadcaster(app))


def fget(app: web.Application) -> Broadcaster:
    return features.get(app, Broadcaster)
