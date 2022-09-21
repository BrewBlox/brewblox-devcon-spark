"""
Regulates actions that should be taken when the service connects to a controller.
"""


import asyncio
from contextlib import suppress
from datetime import datetime
from functools import wraps

from aiohttp import web
from brewblox_service import brewblox_logger, features, repeater, strex

from brewblox_devcon_spark import (block_store, codec, commander, const,
                                   datastore, exceptions, global_store,
                                   service_status, service_store)
from brewblox_devcon_spark.codec.time_utils import serialize_duration
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
        - Synchronize controller settings
            - Send sysTime to controller if mismatched
            - Send temp Unit to controller if mismatched
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
            await self._sync_sysinfo()

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

        return service_status.desc(self.app).controller.device.device_id

    def get_autoconnecting(self) -> bool:
        return service_status.desc(self.app).enabled

    async def set_autoconnecting(self, enabled: bool):
        enabled = bool(enabled)
        service_status.set_enabled(self.app, enabled)
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
            enabled = bool(config.setdefault(AUTOCONNECTING_KEY, True))
            service_status.set_enabled(self.app, enabled)

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

        desc = service_status.desc(self.app)

        if desc.firmware_error == 'INCOMPATIBLE':
            raise exceptions.IncompatibleFirmware()

        if desc.identity_error == 'INVALID':
            raise exceptions.InvalidDeviceId()

    @subroutine('sync block store')
    async def _sync_block_store(self):
        await datastore.check_remote(self.app)
        await self.block_store.read(self.device_name)

    @subroutine('sync controller settings')
    async def _sync_sysinfo(self):
        await self.set_sysinfo_settings()

    async def on_global_store_change(self):
        """Callback invoked by global_store"""
        await self.set_converter_units()

        if await service_status.wait_acknowledged(self.app, wait=False):
            await self.set_sysinfo_settings()

    async def set_converter_units(self):
        converter = codec.unit_conversion.fget(self.app)
        converter.temperature = self.global_store.units['temperature']
        LOGGER.info(f'Service temperature unit set to {converter.temperature}')

    async def set_sysinfo_settings(self):
        sysinfo = await self.commander.read_block(
            FirmwareBlockIdentity(nid=const.SYSINFO_NID))

        uptime = sysinfo.data['uptime']['value']
        LOGGER.info(f'System uptime: {serialize_duration(uptime)}')

        update_freq = sysinfo.data['updatesPerSecond']
        LOGGER.info(f'System updates per second: {update_freq}')

        # Always try and write system time
        patch_data = {'systemTime': datetime.now()}

        # Check system time zone
        user_tz_name = self.global_store.time_zone['name']
        user_tz = self.global_store.time_zone['posixValue']
        block_tz = sysinfo.data['timeZone']

        if user_tz != block_tz:
            LOGGER.info(f'Updating Spark time zone: {user_tz} ({user_tz_name})')
            patch_data['timeZone'] = user_tz

        # Check system temp unit
        user_unit = self.global_store.units['temperature']
        expected_unit = 'TEMP_FAHRENHEIT' if user_unit == 'degF' else 'TEMP_CELSIUS'
        block_unit = sysinfo.data['tempUnit']

        if expected_unit != block_unit:
            LOGGER.info(f'Updating Spark temp unit: {user_unit}')
            patch_data['tempUnit'] = expected_unit

        await self.commander.patch_block(FirmwareBlock(
            nid=const.SYSINFO_NID,
            type='SysInfo',
            data=patch_data,
        ))


def setup(app: web.Application):
    features.add(app, SparkSynchronization(app))


def fget(app: web.Application) -> SparkSynchronization:
    return features.get(app, SparkSynchronization)
