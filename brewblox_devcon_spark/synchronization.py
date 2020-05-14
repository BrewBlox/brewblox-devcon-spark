"""
Regulates actions that should be taken when the service connects to a controller.
"""


import asyncio
from datetime import datetime
from functools import wraps
from time import monotonic

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


def subroutine(desc: str):
    """
    This decorator provides error logging for synchronization routines.
    asyncio.CancelledError is passed through as is.
    Other errors are logged and re-raised.
    """
    def wrapper(func):
        @wraps(func)
        async def wrapped(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except asyncio.CancelledError:  # pragma: no cover
                raise
            except Exception as ex:
                LOGGER.error(f'Failed to {desc} - {strex(ex)}')
                raise ex
        return wrapped
    return wrapper


class Syncher(repeater.RepeaterFeature):

    async def before_shutdown(self, app: web.Application):
        await self.end()

    async def prepare(self):
        """Implements RepeaterFeature.prepare"""
        self._sync_done = asyncio.Event()

    async def run(self):
        """
        This feature continuously manages synchronization between
        the spark service, the spark controller, and the datastore.

        The state machine loops through the following states:
        - Startup
        - Synchronize with datastore
            - Read service-specific data in datastore.
            - Get the 'autoconnecting' value from the service store.
            - Set the autoconnecting event in state.py
        - Connect to controller
            - Wait for 'connect' event to be set by communication.py
        - Synchronize handshake
            - Keep sending a Noop command until 'handshake' event is set
            - Check firmware info in handshake for compatibility
            - Abort synchronization if firmware/ID is not compatible
        - Synchronize block store
            - Read controller-specific data in datastore.
        - Migrate config store
            - Check if service-specific data was already initialized
            - If not, read controller-specific data, and migrate to service store
        - Synchronize controller time
            - Send current abs time to controller block
        - Set 'synchronize' event
        - Wait for 'disconnect' event

        Implements RepeaterFeature.run
        """
        try:
            self._sync_done.clear()
            await self._sync_service_store()

            await state.wait_connect(self.app)
            await self._sync_handshake()
            await self._sync_block_store()
            await self._migrate_config_store()
            await self._sync_time()

            await state.set_synchronize(self.app)
            LOGGER.info('Service synchronized!')

        except asyncio.CancelledError:
            raise

        except asyncio.TimeoutError:
            LOGGER.error('Synchronization timeout. Exiting now...')
            raise web.GracefulExit(1)

        except exceptions.IncompatibleFirmware:
            LOGGER.error('Incompatible firmware version detected')

        except exceptions.InvalidDeviceId:
            LOGGER.error('Invalid device ID detected')

        except Exception as ex:
            LOGGER.error(f'Failed to sync: {strex(ex)}')
            raise web.GracefulExit(1)

        finally:
            self._sync_done.set()

        await state.wait_disconnect(self.app)

    @property
    def device_name(self) -> str:
        # Simulation services are identified by service name
        if self.app['config']['simulation']:
            return 'simulator__' + self.app['config']['name']

        return state.summary(self.app).device.device_id

    @subroutine('sync service store')
    async def _sync_service_store(self):
        service_store = datastore.get_service_store(self.app)
        await datastore.check_remote(self.app)
        await service_store.read()

        with service_store.open() as config:
            enabled = config.setdefault('autoconnecting', True)
            await state.set_autoconnecting(self.app, enabled)

    @subroutine('sync handshake')
    async def _sync_handshake(self):
        start = monotonic()
        handshake_task = await scheduler.create(self.app, state.wait_handshake(self.app))

        while not handshake_task.done():
            if start + HANDSHAKE_TIMEOUT_S < monotonic():
                await scheduler.cancel(self.app, handshake_task)
                raise asyncio.TimeoutError()

            # The noop command will trigger a handshake
            # Keep sending until we get a handshake
            await get_controller(self.app).noop()
            await asyncio.wait([handshake_task, asyncio.sleep(PING_INTERVAL_S)],
                               return_when=asyncio.FIRST_COMPLETED)

        summary = state.summary(self.app)

        if not summary.compatible:
            raise exceptions.IncompatibleFirmware()

        if not summary.valid:
            raise exceptions.InvalidDeviceId()

    @subroutine('sync block store')
    async def _sync_block_store(self):
        block_store = datastore.get_block_store(self.app)
        await datastore.check_remote(self.app)
        await block_store.read(self.device_name)

    @subroutine('migrate config store')
    async def _migrate_config_store(self):
        service_store = datastore.get_service_store(self.app)
        config_store = datastore.CouchDBConfigStore(self.app)

        with service_store.open() as new_config:
            if new_config.get('version') != 'v1':
                # We don't need to re-check datastore availability
                await config_store.startup(self.app)
                await config_store.read(self.device_name)
                with config_store.open() as old_config:
                    LOGGER.info('Migrating to service config...')
                    new_config.update(**{
                        **old_config,
                        **new_config,
                        'version': 'v1'
                    })
                await config_store.shutdown(self.app)

    @subroutine('sync controller time')
    async def _sync_time(self):
        now = datetime.now()
        api = object_api.ObjectApi(self.app, wait_sync=False)
        await api.write(
            sid=datastore.SYSTIME_NID,
            groups=[SYSTEM_GROUP],
            input_type='Ticks',
            input_data={
                'secondsSinceEpoch': now.timestamp()
            })


def setup(app: web.Application):
    features.add(app, Syncher(app))


def get_syncher(app: web.Application) -> Syncher:
    return features.get(app, Syncher)
