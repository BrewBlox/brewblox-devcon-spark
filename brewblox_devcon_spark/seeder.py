"""
Regulates actions that should be taken when the service connects to a controller.
"""


import asyncio
import warnings
from datetime import datetime

from aiohttp import web
from brewblox_service import brewblox_logger, features, scheduler, strex

from brewblox_devcon_spark import datastore, status
from brewblox_devcon_spark.api import object_api
from brewblox_devcon_spark.device import SYSTEM_GROUP

LOGGER = brewblox_logger(__name__)


def setup(app: web.Application):
    features.add(app, Seeder(app))


def get_seeder(app: web.Application):
    return features.get(app, Seeder)


class Seeder(features.ServiceFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)

        self._config = app['config']
        self._task: asyncio.Task = None
        self._seeding_done: asyncio.Event = None

    @property
    def active(self):
        return self._task and not self._task.done()

    async def startup(self, app: web.Application):
        await self.shutdown(app)
        self._task = await scheduler.create_task(app, self._seed())
        self._seeding_done = asyncio.Event()

    async def shutdown(self, _):
        await scheduler.cancel_task(self.app, self._task)
        self._task = None

    async def _seed(self):
        spark_status = status.get_status(self.app)

        while True:
            try:
                self._seeding_done.clear()
                await spark_status.wait_matched()
                await self._seed_datastore()
                await self._seed_time()
                await spark_status.on_synchronize()

            except asyncio.CancelledError:
                raise

            except Exception as ex:
                LOGGER.error(f'Failed to seed: {strex(ex)}')

            finally:
                self._seeding_done.set()

            await spark_status.wait_disconnected()

    async def seeding_done(self):
        return await self._seeding_done.wait()

    ##########

    async def _seed_datastore(self):
        try:
            api = object_api.ObjectApi(self.app, wait_sync=False)
            sys_block = await api.read(datastore.SYSINFO_NID)
            device_id = sys_block[object_api.API_DATA_KEY]['deviceId']

            await datastore.check_remote(self.app)
            await asyncio.gather(
                datastore.get_datastore(self.app).read(f'{device_id}-blocks-db'),
                datastore.get_config(self.app).read(f'{device_id}-config-db'),
            )

        except Exception as ex:
            warnings.warn(f'Failed to seed datastore - {type(ex).__name__}({ex})')
            raise

    async def _seed_time(self):
        try:
            now = datetime.now()
            api = object_api.ObjectApi(self.app, wait_sync=False)
            await api.write(
                sid=datastore.SYSTIME_NID,
                groups=[SYSTEM_GROUP],
                input_type='Ticks',
                input_data={
                    'secondsSinceEpoch': now.timestamp()
                })

        except Exception as ex:
            warnings.warn(f'Failed to seed controller time - {type(ex).__name__}({ex})')
            raise
