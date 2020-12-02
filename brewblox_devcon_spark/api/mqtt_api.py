"""
MQTT API for Spark blocks
"""

from functools import wraps

from aiohttp import web
from brewblox_service import brewblox_logger, features, mqtt

from brewblox_devcon_spark.api import blocks_api, schemas

LOGGER = brewblox_logger(__name__)


BLOCKS_TOPIC = 'brewcast/spark/blocks'


def validated(schema):
    def wrapper(func):
        @wraps(func)
        async def wrapped(self, topic, data):
            errors = schema().validate(data)
            if errors:
                LOGGER.error(f'Invalid MQTT call: {topic} {errors}')
                return
            if data.get('serviceId') != self.name:
                return
            return await func(self,  data)
        return wrapped
    return wrapper


class MqttApi(features.ServiceFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)
        self.name = app['config']['name']
        self.api = blocks_api.BlocksApi(self.app)
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

    @validated(schemas.BlockSchema)
    async def _create(self, block: dict):
        await self.api.create(block)

    @validated(schemas.BlockSchema)
    async def _write(self, block: dict):
        await self.api.write(block)

    @validated(schemas.BlockPatchSchema)
    async def _patch(self, patch: dict):
        await self.api.patch(patch)

    @validated(schemas.BlockIdSchema)
    async def _delete(self, args: dict):
        await self.api.delete(args)


def setup(app: web.Application):
    features.add(app, MqttApi(app))


def fget(app: web.Application) -> MqttApi:
    return features.get(app, MqttApi)
