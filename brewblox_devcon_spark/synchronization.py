"""
This feature continuously manages synchronization between
the spark service, the spark controller, and the datastore.

After startup, `connection` and `synchronization` cooperate to
advance a state machine. The state machine will progress linearly,
but may revert to DISCONNECTED at any time.

This state machine is disabled if `enabled` is False in service settings.
`connection` will wait until enabled before it attempts to discover and connect.

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

- Set enabled flag to `service_settings.enabled` value.
- Wait for CONNECTED status.
- Synchronize handshake:
    - Repeatedly prompt the controller to send a handshake,
        until status is ACKNOWLEDGED.
    - Verify that the service is compatible with the controller.
    - If the controller is not compatible, abort synchronization.
- Synchronize controller settings:
    - Send timezone to controller.
    - Send temperature display units to controller.
    - Get block names from controller.
- Set status to SYNCHRONIZED.
- Wait for DISCONNECTED status.
- Repeat
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from functools import wraps

from . import (codec, command, const, datastore_blocks, datastore_settings,
               exceptions, state_machine, utils)
from .codec.time_utils import serialize_duration
from .models import FirmwareBlock, FirmwareBlockIdentity

LOGGER = logging.getLogger(__name__)


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
                LOGGER.error(f'Sync subroutine failed: {desc} - {utils.strex(ex)}')
                raise ex
        return wrapped
    return wrapper


class StateSynchronizer:

    def __init__(self):
        self.config = utils.get_config()
        self.state = state_machine.CV.get()
        self.settings_store = datastore_settings.CV.get()
        self.block_store = datastore_blocks.CV.get()
        self.converter = codec.unit_conversion.CV.get()
        self.commander = command.CV.get()

    @subroutine('apply global settings')
    async def _apply_global_settings(self):
        await self.set_converter_units()

        # This function may be invoked as a callback by datastore
        # Here, we don't know if we're synchronized
        if self.state.is_synchronized():
            await self.set_sysinfo_settings()

    @subroutine('apply service settings')
    async def _apply_service_settings(self):
        enabled = self.settings_store.service_settings.enabled
        self.state.set_enabled(enabled)

    async def _prompt_handshake(self):
        try:
            LOGGER.info('prompting handshake...')
            await self.commander.version()
        except Exception as ex:
            LOGGER.debug(f'Handshake prompt error: {utils.strex(ex)}', exc_info=True)

    @subroutine('sync handshake')
    async def _sync_handshake(self):
        # Periodically prompt a handshake until acknowledged by the controller
        async with asyncio.timeout(self.config.handshake_timeout.total_seconds()):
            async with utils.task_context(self.state.wait_acknowledged()) as ack_task:
                while not ack_task.done():
                    await self._prompt_handshake()
                    # Returns early if acknowledged before timeout elapsed
                    await asyncio.wait([ack_task],
                                       timeout=self.config.handshake_ping_interval.total_seconds())

        self.state.check_compatible()

    @subroutine('sync block store')
    async def _sync_block_store(self):
        blocks = await self.commander.read_all_block_names()
        self.block_store.clear()
        for block in blocks:
            self.block_store[block.id] = block.nid

        # Check if redis still contains a name table for this controller's blocks
        # If it does, attempt to load block names
        # This is a one-time migration. The redis table is removed after reading.
        for entry in await datastore_blocks.extract_legacy_redis_block_names():  # pragma: no cover
            sid, nid = entry
            LOGGER.info(f'Renaming block to legacy name: {sid=}, {nid=}')
            try:
                await self.commander.write_block_name(FirmwareBlockIdentity(id=sid, nid=nid))
                self.block_store[sid] = nid
            except Exception as ex:
                LOGGER.info(f'Failed to rename block {entry}: {utils.strex(ex)}')

    @subroutine('sync controller settings')
    async def _sync_sysinfo(self):
        await self.set_sysinfo_settings()

    async def set_converter_units(self):
        self.converter.temperature = self.settings_store.unit_settings.temperature
        LOGGER.info(f'Service temperature unit set to {self.converter.temperature}')

    async def set_sysinfo_settings(self):
        # Get time zone
        tz_name = self.settings_store.timezone_settings.name
        tz_posix = self.settings_store.timezone_settings.posixValue
        LOGGER.info(f'Spark time zone: {tz_posix} ({tz_name})')

        # Get temp unit
        temp_unit_name = self.settings_store.unit_settings.temperature
        temp_unit_enum = 'TEMP_FAHRENHEIT' if temp_unit_name == 'degF' else 'TEMP_CELSIUS'
        LOGGER.info(f'Spark temp unit: {temp_unit_enum}')

        sysinfo = await self.commander.patch_block(
            FirmwareBlock(
                nid=const.SYS_BLOCK_IDS['SysInfo'],
                type=const.SYSINFO_BLOCK_TYPE,
                data={
                    'timeZone': tz_posix,
                    'tempUnit': temp_unit_enum,
                },
            ))

        if sysinfo.type != const.SYSINFO_BLOCK_TYPE:
            raise exceptions.CommandException(f'Unexpected SysInfo block: {sysinfo}')

        uptime = sysinfo.data['uptime']['value']
        LOGGER.info(f'Spark uptime: {serialize_duration(uptime)}')

        update_freq = sysinfo.data['updatesPerSecond']
        LOGGER.info(f'Spark updates per second: {update_freq}')

    async def synchronize(self):
        await self._apply_global_settings()
        await self._apply_service_settings()
        await self.state.wait_connected()
        await self._sync_handshake()
        await self._sync_block_store()
        await self._sync_sysinfo()
        self.state.set_synchronized()

    async def run(self):
        try:
            await self.synchronize()

        except exceptions.IncompatibleFirmware:
            LOGGER.error('Incompatible firmware version detected')

        except exceptions.InvalidDeviceId:
            LOGGER.error('Invalid device ID detected')

        except Exception as ex:
            LOGGER.error(f'Failed to sync: {utils.strex(ex)}')
            await self.commander.reset_connection()

        await self.state.wait_disconnected()

    async def repeat(self):
        self.settings_store.service_settings_listeners.add(self._apply_service_settings)
        self.settings_store.global_settings_listeners.add(self._apply_global_settings)
        while True:
            await self.run()


@asynccontextmanager
async def lifespan():
    sync = StateSynchronizer()
    async with utils.task_context(sync.repeat()):
        yield
