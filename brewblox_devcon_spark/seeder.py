"""
Regulates actions that should be taken when the service connects to a controller.
"""


import asyncio
import warnings
from datetime import datetime

from aiohttp import web
from brewblox_service import brewblox_logger, features, scheduler

from brewblox_devcon_spark import datastore, status
from brewblox_devcon_spark.api import object_api

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

    @property
    def active(self):
        return self._task and not self._task.done()

    async def startup(self, app: web.Application):
        await self.shutdown(app)
        self._task = await scheduler.create_task(app, self._seed())

    async def shutdown(self, _):
        await scheduler.cancel_task(self.app, self._task)
        self._task = None

    async def _seed(self):
        spark_status = status.get_status(self.app)

        while True:
            await spark_status.connected.wait()
            await self._seed_datastore()
            await self._seed_time()
            spark_status.synchronized.set()

            await spark_status.disconnected.wait()
            spark_status.synchronized.clear()

    ##########

    async def _seed_datastore(self):
        try:
            api = object_api.ObjectApi(self.app, wait_sync=False)
            sys_block = await api.read(datastore.SYSINFO_CONTROLLER_ID)
            device_id = sys_block[object_api.API_DATA_KEY]['deviceId']

            await asyncio.gather(
                datastore.get_datastore(self.app).read(f'{device_id}-blocks-db'),
                datastore.get_config(self.app).read(f'{device_id}-config-db'),
            )

        except asyncio.CancelledError:
            raise

        except Exception as ex:
            warnings.warn(f'Failed to seed datastore - {type(ex).__name__}({ex})')

    async def _seed_time(self):
        try:
            now = datetime.now()
            api = object_api.ObjectApi(self.app, wait_sync=False)
            await api.write(
                input_id=datastore.TIME_CONTROLLER_ID,
                profiles=[i for i in range(8)],
                input_type='Ticks',
                input_data={
                    'secondsSinceEpoch': now.timestamp()
                })

        except asyncio.CancelledError:
            raise

        except Exception as ex:
            warnings.warn(f'Failed to seed controller time - {type(ex).__name__}({ex})')
