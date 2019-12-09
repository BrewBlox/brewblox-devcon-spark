"""
Regulates actions that should be taken when the service connects to a controller.
"""


import asyncio
from datetime import datetime

from aiohttp import web
from brewblox_service import brewblox_logger, features, scheduler, strex

from brewblox_devcon_spark import datastore, exceptions, state
from brewblox_devcon_spark.api import object_api
from brewblox_devcon_spark.device import get_controller
from brewblox_devcon_spark.validation import SYSTEM_GROUP

HANDSHAKE_TIMEOUT_S = 30
PING_INTERVAL_S = 1

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
        ping_task = None

        while True:
            try:
                self._seeding_done.clear()
                await state.wait_connect(self.app)
                # Will trigger the backup handshake
                # We don't need to wait for this - we just want the side effect
                ping_task = await scheduler.create_task(self.app, self._ping_controller())

                await asyncio.wait_for(state.wait_handshake(self.app), HANDSHAKE_TIMEOUT_S)
                await scheduler.cancel_task(self.app, ping_task, wait_for=False)

                summary = state.summary(self.app)

                if not summary.compatible:  # pragma: no cover
                    raise exceptions.IncompatibleFirmware()

                if not summary.valid:  # pragma: no cover
                    raise exceptions.InvalidDeviceId()

                await self._seed_datastore()
                await self._seed_time()

                await state.on_synchronize(self.app)
                LOGGER.info('Service synchronized!')

            except asyncio.CancelledError:
                raise

            except asyncio.TimeoutError:
                LOGGER.error('Seeding timeout. Exiting now...')
                raise SystemExit(1)

            except exceptions.IncompatibleFirmware:  # pragma: no cover
                LOGGER.error('Incompatible firmware version detected')

            except exceptions.InvalidDeviceId:  # pragma: no cover
                LOGGER.error('Invalid device ID detected')

            except Exception as ex:
                LOGGER.error(f'Failed to seed: {strex(ex)}')
                raise SystemExit(1)

            finally:
                self._seeding_done.set()
                await scheduler.cancel_task(self.app, ping_task)

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
                LOGGER.debug('Cancelled handshake ping')
                return

            except Exception as ex:  # pragma: no cover
                LOGGER.error(f'Failed to ping controller - {strex(ex)}')
                return

    async def _seed_datastore(self):
        try:
            device_id = state.get_status(self.app).device.device_id

            await datastore.check_remote(self.app)
            await asyncio.gather(
                datastore.get_datastore(self.app).read(f'{device_id}-blocks-db'),
                datastore.get_config(self.app).read(f'{device_id}-config-db'),
            )

        except asyncio.CancelledError:  # pragma: no cover
            LOGGER.debug('Cancelled datastore seeding')
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
            LOGGER.debug('Cancelled time seeding')
            raise

        except Exception as ex:
            LOGGER.error(f'Failed to seed controller time - {strex(ex)}')
            raise ex
