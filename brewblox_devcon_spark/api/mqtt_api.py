"""
MQTT API for Spark blocks
"""

import json

from aiohttp import web
from brewblox_service import brewblox_logger, features, mqtt

from brewblox_devcon_spark import controller
from brewblox_devcon_spark.models import Block, BlockIdentity

LOGGER = brewblox_logger(__name__)

BLOCKS_TOPIC = 'brewcast/spark/blocks'


class MqttApi(features.ServiceFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)
        self.name = app['config']['name']
        self.controller = controller.fget(app)
        self.listeners = {
            '/create': self._create,
            '/write': self._write,
            '/patch': self._patch,
            '/delete': self._delete,
        }

    async def startup(self, app: web.Application):
        for path, listener in self.listeners.items():
            await mqtt.listen(app, BLOCKS_TOPIC + path, listener)
        await mqtt.subscribe(app, BLOCKS_TOPIC + '/#')

    async def shutdown(self, app: web.Application):
        await mqtt.unsubscribe(app, BLOCKS_TOPIC + '/#')
        for path, listener in self.listeners.items():
            await mqtt.unlisten(app, BLOCKS_TOPIC + path, listener)

    async def _create(self, topic: str, msg: str):
        block = Block(**json.loads(msg))
        if block.serviceId == self.name:
            await self.controller.create_block(block)

    async def _write(self, topic: str, msg: str):
        block = Block(**json.loads(msg))
        if block.serviceId == self.name:
            await self.controller.write_block(block)

    async def _patch(self, topic: str, msg: str):
        block = Block(**json.loads(msg))
        if block.serviceId == self.name:
            await self.controller.patch_block(block)

    async def _delete(self, topic: str, msg: str):
        ident = BlockIdentity(**json.loads(msg))
        if ident.serviceId == self.name:
            await self.controller.delete_block(ident)


def setup(app: web.Application):
    features.add(app, MqttApi(app))


def fget(app: web.Application) -> MqttApi:
    return features.get(app, MqttApi)
