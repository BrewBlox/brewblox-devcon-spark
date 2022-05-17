"""
Regulates actions that should be taken when the service connects to a controller.
"""


import asyncio
from contextlib import suppress
from datetime import datetime, timedelta
from functools import wraps

from aiohttp import web
from brewblox_service import brewblox_logger, features, repeater, strex

from brewblox_devcon_spark import (block_store, codec, commander, const,
                                   datastore, exceptions, global_store,
                                   service_status, service_store)
from brewblox_devcon_spark.models import FirmwareBlock, FirmwareBlockIdentity

HANDSHAKE_TIMEOUT_S = 120
PING_INTERVAL_S = 1
UNIT_CONFIG_KEY = 'user_units'
AUTOCONNECTING_KEY = 'autoconnecting'

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
            except Exception as ex:
                LOGGER.error(f'Sync subroutine failed: {desc} - {strex(ex)}')
                raise ex
        return wrapped
    return wrapper


class SparkSynchronization(repeater.RepeaterFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)
        self.codec = codec.fget(app)
        self.commander = commander.fget(app)
        self.service_store = service_store.fget(self.app)
        self.global_store = global_store.fget(self.app)
        self.block_store = block_store.fget(self.app)

    async def before_shutdown(self, app: web.Application):
        await self.end()

    async def prepare(self):
        """Implements RepeaterFeature.prepare"""
        global_store.fget(self.app).listeners.add(self.on_global_store_change)

    async def run(self):
        """
        This feature continuously manages synchronization between
        the spark service, the spark controller, and the datastore.

        The state machine loops through the following states:
        - Startup
        - Synchronize with datastore
            - Read global data in datastore
            - Set temperature unit in codec/unit_conversion.py
            - Read service-specific data in datastore
            - Get the 'autoconnecting' value from the service store
            - Set the autoconnecting event in state.py
        - Connect to controller
            - Wait for 'connected' event to be set by connection.py
        - Synchronize handshake
            - Keep sending a Version command until 'acknowledged' event is set
            - Check firmware info in handshake for compatibility
            - Abort synchronization if firmware/ID is not compatible
        - Synchronize block store
            - Read controller-specific data in datastore
        - Synchronize controller time
            - Send current abs time to controller block
        - Synchronize controller display unit
            - Send correct unit to controller if mismatched
            - Send timezone to controller if mismatched
        - Set 'synchronized' event
        - Wait for 'disconnected' event

        Implements RepeaterFeature.run
        """
        try:
            await self._sync_datastore()

            await service_status.wait_connected(self.app)
            await self._sync_handshake()
            await self._sync_block_store()
            await self._sync_time()
            await self._sync_display()

            service_status.set_synchronized(self.app)
            LOGGER.info('Service synchronized!')

        except exceptions.IncompatibleFirmware:
            LOGGER.error('Incompatible firmware version detected')

        except exceptions.InvalidDeviceId:
            LOGGER.error('Invalid device ID detected')

        except Exception as ex:
            LOGGER.error(f'Failed to sync: {strex(ex)}')
            await commander.fget(self.app).start_reconnect()
            raise ex

        await service_status.wait_disconnected(self.app)

    @property
    def device_name(self) -> str:
        # Simulation services are identified by service name
        if self.app['config']['simulation']:
            return 'simulator__' + self.app['config']['name']

        return service_status.desc(self.app).device_info.device_id

    def get_autoconnecting(self):
        return service_status.desc(self.app).is_autoconnecting

    async def set_autoconnecting(self, enabled):
        enabled = bool(enabled)
        service_status.set_autoconnecting(self.app, enabled)
        with service_store.fget(self.app).open() as config:
            config[AUTOCONNECTING_KEY] = enabled
        return enabled

    @subroutine('sync datastore')
    async def _sync_datastore(self):

        await datastore.check_remote(self.app)
        await self.service_store.read()
        await self.global_store.read()

        await self.set_converter_units()

        with self.service_store.open() as config:
            autoconnect = bool(config.setdefault(AUTOCONNECTING_KEY, True))
            service_status.set_autoconnecting(self.app, autoconnect)

            # Units were moved to global config (2021/04/02)
            with suppress(KeyError):
                del config[UNIT_CONFIG_KEY]

    @subroutine('sync handshake')
    async def _sync_handshake(self):
        """
        Wait for the controller to acknowledge the connection with a handshake,
        while sending prompts by using the Noop command.

        If no handshake is received after `HANDSHAKE_TIMEOUT_S`,
        an asyncio.TimeoutError is raised.

        The handshake is checked, and appropriate errors are raised
        if the device ID or firmware version are incompatible.
        """

        async def prompt_handshake():
            while True:
                try:
                    await asyncio.sleep(PING_INTERVAL_S)
                    LOGGER.info('prompting handshake...')
                    await self.commander.version()
                except Exception as ex:
                    LOGGER.error(strex(ex))
                    pass

        ack_wait_task = asyncio.create_task(service_status.wait_acknowledged(self.app))
        prompt_task = asyncio.create_task(prompt_handshake())

        await asyncio.wait([ack_wait_task, prompt_task],
                           return_when=asyncio.FIRST_COMPLETED,
                           timeout=HANDSHAKE_TIMEOUT_S)

        # asyncio.wait() does not cancel tasks
        # cancel() can be safely called if the task is already done
        ack_wait_task.cancel()
        prompt_task.cancel()

        if not await service_status.wait_acknowledged(self.app, wait=False):
            raise asyncio.TimeoutError()

        handshake = service_status.desc(self.app).handshake_info

        if not handshake.is_compatible_firmware:
            raise exceptions.IncompatibleFirmware()

        if not handshake.is_valid_device_id:
            raise exceptions.InvalidDeviceId()

    @subroutine('sync block store')
    async def _sync_block_store(self):
        await datastore.check_remote(self.app)
        await self.block_store.read(self.device_name)

    @subroutine('sync controller time')
    async def _sync_time(self):
        now = datetime.now()
        ticks_block = await self.commander.read_block(
            FirmwareBlock(
                nid=const.SYSTIME_NID,
                type='Ticks',
                data={
                    'secondsSinceEpoch': int(now.timestamp())
                }
            ))
        ms = ticks_block.data['millisSinceBoot']
        uptime = timedelta(milliseconds=ms)
        LOGGER.info(f'System uptime: {uptime}')

    @subroutine('sync display settings')
    async def _sync_display(self):
        await self.set_display_settings()

    async def on_global_store_change(self):
        """Callback invoked by global_store"""
        await self.set_converter_units()
        await self.set_display_settings()

    async def set_converter_units(self):
        converter = codec.unit_conversion.fget(self.app)
        converter.temperature = self.global_store.units['temperature']
        LOGGER.info(f'Service temperature unit set to {converter.temperature}')

    async def set_display_settings(self):
        write_required = False

        if not service_status.desc(self.app).is_acknowledged:
            return

        display_block = await self.commander.read_block(
            FirmwareBlockIdentity(nid=const.DISPLAY_SETTINGS_NID))

        user_unit = self.global_store.units['temperature']
        expected_unit = 'TEMP_FAHRENHEIT' if user_unit == 'degF' else 'TEMP_CELSIUS'
        block_unit = display_block.data['tempUnit']

        if expected_unit != block_unit:
            write_required = True
            display_block.data['tempUnit'] = expected_unit
            LOGGER.info(f'Spark display temperature unit set to {user_unit}')

        user_tz_name = self.global_store.time_zone['name']
        user_tz = self.global_store.time_zone['posixValue']
        block_tz = display_block.data['timeZone']

        if user_tz != block_tz:
            write_required = True
            display_block.data['timeZone'] = user_tz
            LOGGER.info(f'Spark display time zone set to {user_tz} ({user_tz_name})')

        if write_required:
            await self.commander.write_block(display_block)


def setup(app: web.Application):
    features.add(app, SparkSynchronization(app))


def fget(app: web.Application) -> SparkSynchronization:
    return features.get(app, SparkSynchronization)
