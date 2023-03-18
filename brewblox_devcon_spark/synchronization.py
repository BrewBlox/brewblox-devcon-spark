"""
This feature continuously manages synchronization between
the spark service, the spark controller, and the datastore.

At startup, configuration is fetched from the datastore.
For the global datastore, change callbacks are in place.
This service will be the only one to change any of the other settings,
and does not need to be notified of external changes.

After startup, `connection` and `synchronization` cooperate to
advance a state machine. The state machine will progress linearly,
but may revert to DISCONNECTED at any time.

- DISCONNECTED: The service is not connected at a transport level.
- CONNECTED: The service is connected at a transport level,
    but has not yet received a handshake.
- ACKNOWLEDGED: The service has received a handshake.
    If the firmware described in the handshake is incompatible
    with the service, the process stops here.
    If the firmware is compatible, configuration is synchronized.
- SYNCHRONIZED: The service API is ready for use.
- UPDATING: The service is still connected to the controller,
    but has initiated a firmware update.
    Block API calls will immediately return an error.

The synchronization process consists of:

- Wait for CONNECTED status.
- Synchronize handshake:
    - Repeatedly prompt the controller to send a handshake,
        until status is ACKNOWLEDGED.
    - Verify that the service is compatible with the controller.
    - If the controller is not compatible, abort synchronization.
- Synchronize block store:
    - Fetch controller-specific data from datastore.
- Synchronize controller settings:
    - Send timezone to controller.
    - Send temperature display units to controller.
- Set status to SYNCHRONIZED.
- Wait for DISCONNECTED status.
- Repeat
"""


import asyncio
from functools import wraps

from aiohttp import web
from async_timeout import timeout
from brewblox_service import brewblox_logger, features, repeater, strex

from brewblox_devcon_spark import (block_store, codec, commander, const,
                                   datastore, exceptions, global_store,
                                   service_status, service_store)
from brewblox_devcon_spark.codec.time_utils import serialize_duration
from brewblox_devcon_spark.models import FirmwareBlock

HANDSHAKE_TIMEOUT_S = 120
PING_INTERVAL_S = 2

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
        # One-time datastore synchronization
        await self._sync_datastore()

    async def run(self):
        try:
            await service_status.wait_connected(self.app)
            await self.synchronize()

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
        # Simulation services are identified by service name.
        # This prevents data conflicts when a simulation service
        # is reconfigured to start interacting with a controller.
        if self.app['config']['simulation']:
            return 'simulator__' + self.app['config']['name']

        return service_status.desc(self.app).controller.device.device_id

    async def synchronize(self):
        await self._sync_handshake()
        await self._sync_block_store()
        await self._sync_sysinfo()
        service_status.set_synchronized(self.app)

    @subroutine('sync datastore')
    async def _sync_datastore(self):
        self.global_store.listeners.add(self.on_global_store_change)
        await datastore.check_remote(self.app)
        await self.service_store.read()
        await self.global_store.read()

        await self.set_converter_units()

        autoconnecting = service_store.get_autoconnecting(self.app)
        service_status.set_enabled(self.app, autoconnecting)

    async def _prompt_handshake(self):
        try:
            LOGGER.info('prompting handshake...')
            await self.commander.version()
        except Exception as ex:
            LOGGER.debug(f'Handshake prompt error: {strex(ex)}')

    @subroutine('sync handshake')
    async def _sync_handshake(self):
        # Simultaneously prompt a handshake, and wait for it to be received
        ack_task = asyncio.create_task(service_status.wait_acknowledged(self.app))
        try:
            async with timeout(HANDSHAKE_TIMEOUT_S):
                while not ack_task.done():
                    await self._prompt_handshake()
                    await asyncio.wait([ack_task], timeout=PING_INTERVAL_S)
        finally:
            ack_task.cancel()

        ack_task.result()
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

        if await service_status.wait_synchronized(self.app, wait=False):
            await self.set_sysinfo_settings()

    async def set_converter_units(self):
        converter = codec.unit_conversion.fget(self.app)
        converter.temperature = self.global_store.units['temperature']
        LOGGER.info(f'Service temperature unit set to {converter.temperature}')

    async def set_sysinfo_settings(self):
        # Get time zone
        tz_name = self.global_store.time_zone['name']
        tz_posix = self.global_store.time_zone['posixValue']
        LOGGER.info(f'Spark time zone: {tz_posix} ({tz_name})')

        # Get temp unit
        temp_unit_name = self.global_store.units['temperature']
        temp_unit_enum = 'TEMP_FAHRENHEIT' if temp_unit_name == 'degF' else 'TEMP_CELSIUS'
        LOGGER.info(f'Spark temp unit: {temp_unit_enum}')

        sysinfo = await self.commander.patch_block(
            FirmwareBlock(
                nid=const.SYSINFO_NID,
                type='SysInfo',
                data={
                    'timeZone': tz_posix,
                    'tempUnit': temp_unit_enum,
                },
            ))

        uptime = sysinfo.data['uptime']['value']
        LOGGER.info(f'Spark uptime: {serialize_duration(uptime)}')

        update_freq = sysinfo.data['updatesPerSecond']
        LOGGER.info(f'Spark updates per second: {update_freq}')


def setup(app: web.Application):
    features.add(app, SparkSynchronization(app))


def fget(app: web.Application) -> SparkSynchronization:
    return features.get(app, SparkSynchronization)
