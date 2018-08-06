"""
Regulates actions that should be taken when the service connects to a controller.
"""


import asyncio
import json

from aiohttp import web
from brewblox_service import brewblox_logger, features, scheduler

from brewblox_devcon_spark import status, twinkeydict
from brewblox_devcon_spark.api import (API_DATA_KEY, API_ID_KEY,
                                       API_PROFILE_LIST_KEY, API_TYPE_KEY,
                                       object_api, profile_api)

LOGGER = brewblox_logger(__name__)


def setup(app: web.Application):
    features.add(app, Seeder(app))


def get_seeder(app: web.Application):
    return features.get(app, Seeder)


class Seeder(features.ServiceFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)
        config = app['config']

        self._task: asyncio.Task = None
        self._profiles = config['seed_profiles']
        self._seeds = []

        if config['seed_objects']:
            with open(config['seed_objects']) as f:
                self._seeds = json.load(f)

    async def startup(self, app: web.Application):
        await self.shutdown(app)
        self._task = await scheduler.create_task(app, self._seed_on_connected())

    async def shutdown(self, _):
        await scheduler.cancel_task(self.app, self._task)
        self._task = None

    async def _seed_on_connected(self):
        spark_status = status.get_status(self.app)

        while True:
            await spark_status.connected.wait()
            await self._seed_objects()
            await self._seed_profiles()
            await spark_status.disconnected.wait()

    async def _seed_objects(self):
        api = object_api.ObjectApi(self.app)
        for seed in self._seeds:
            try:
                id = seed[API_ID_KEY]
                await api.create(
                    id,
                    seed[API_PROFILE_LIST_KEY],
                    seed[API_TYPE_KEY],
                    seed[API_DATA_KEY]
                )
                LOGGER.info(f'Seeded [{id}]')

            except twinkeydict.TwinKeyError:
                LOGGER.warn(f'Aborted seeding [{id}]: duplicate name, or already created')

            except Exception as ex:
                LOGGER.warn(f'Failed to seed object: {type(ex).__name__}({ex})')

    async def _seed_profiles(self):
        if self._profiles:
            LOGGER.info(f'Seeding profiles as {self._profiles}')
            api = profile_api.ProfileApi(self.app)
            await api.write_active(self._profiles)
