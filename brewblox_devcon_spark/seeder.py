"""
Regulates actions that should be taken when the service connects to a controller.
"""


import asyncio
from datetime import datetime

from aiohttp import web
from brewblox_service import (brewblox_logger, features, repeater, scheduler,
                              strex)

from brewblox_devcon_spark import datastore, exceptions, state
from brewblox_devcon_spark.api import object_api
from brewblox_devcon_spark.device import get_controller
from brewblox_devcon_spark.validation import SYSTEM_GROUP

HANDSHAKE_TIMEOUT_S = 30
PING_INTERVAL_S = 1

LOGGER = brewblox_logger(__name__)


class Seeder(repeater.RepeaterFeature):

    async def before_shutdown(self, app: web.Application):
        await self.end()

    async def prepare(self):
        self._seeding_done = asyncio.Event()

    async def run(self):
        ping_task = None

        try:
            self._seeding_done.clear()
            await state.wait_connect(self.app)
            # Will trigger the backup handshake
            # We don't need to wait for this - we just want the side effect
            ping_task = await scheduler.create(self.app, self._ping_controller())

            await asyncio.wait_for(state.wait_handshake(self.app), HANDSHAKE_TIMEOUT_S)
            await scheduler.cancel(self.app, ping_task, wait_for=False)

            summary = state.summary(self.app)

            if not summary.compatible:  # pragma: no cover
                raise exceptions.IncompatibleFirmware()

            if not summary.valid:  # pragma: no cover
                raise exceptions.InvalidDeviceId()

            await self._seed_datastore()
            await self._seed_time()

            await state.set_synchronize(self.app)
            LOGGER.info('Service synchronized!')

        except asyncio.CancelledError:
            raise

        except asyncio.TimeoutError:
            LOGGER.error('Seeding timeout. Exiting now...')
            raise web.GracefulExit(1)

        except exceptions.IncompatibleFirmware:  # pragma: no cover
            LOGGER.error('Incompatible firmware version detected')

        except exceptions.InvalidDeviceId:  # pragma: no cover
            LOGGER.error('Invalid device ID detected')

        except Exception as ex:
            LOGGER.error(f'Failed to seed: {strex(ex)}')
            raise web.GracefulExit(1)

        finally:
            self._seeding_done.set()
            LOGGER.debug('Cancelling ping_task')
            await scheduler.cancel(self.app, ping_task, wait_for=False)

        await state.wait_disconnect(self.app)

    async def seeding_done(self):
        return await self._seeding_done.wait()

    ##########

    async def _ping_controller(self):
        while True:
            try:
                await asyncio.sleep(PING_INTERVAL_S)
                await get_controller(self.app).noop()

            except asyncio.CancelledError:  # pragma: no cover
                raise

            except Exception as ex:  # pragma: no cover
                LOGGER.error(f'Failed to ping controller - {strex(ex)}')
                return

    async def _seed_datastore(self):
        try:
            name = state.summary(self.app).device.device_id

            # Simulation services are identified by service name
            if self.app['config']['simulation']:
                name = 'simulator__' + self.app['config']['name']

            await datastore.check_remote(self.app)
            await asyncio.gather(
                datastore.get_datastore(self.app).read(f'{name}-blocks-db'),
                datastore.get_config(self.app).read(f'{name}-config-db'),
            )

        except asyncio.CancelledError:  # pragma: no cover
            raise

        except Exception as ex:
            LOGGER.error(f'Failed to seed datastore - {strex(ex)}')
            raise ex

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

        except asyncio.CancelledError:  # pragma: no cover
            raise

        except Exception as ex:
            LOGGER.error(f'Failed to seed controller time - {strex(ex)}')
            raise ex


def setup(app: web.Application):
    features.add(app, Seeder(app))


def get_seeder(app: web.Application) -> Seeder:
    return features.get(app, Seeder)
