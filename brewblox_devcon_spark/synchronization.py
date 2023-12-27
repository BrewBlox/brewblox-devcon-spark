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
import logging
import traceback
from contextlib import asynccontextmanager
from functools import wraps

from . import (codec, commander, connection, const, exceptions, state_machine,
               utils)
from .codec.time_utils import serialize_duration
from .datastore import block_store, settings_store
from .models import FirmwareBlock

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


class SparkSynchronization:

    def __init__(self):
        self.config = utils.get_config()
        self.state = state_machine.CV.get()
        self.settings_store = settings_store.CV.get()
        self.block_store = block_store.CV.get()
        self.converter = codec.unit_conversion.CV.get()
        self.connection = connection.CV.get()
        self.commander = commander.CV.get()

    @property
    def device_name(self) -> str:
        # Simulation services are identified by service name.
        # This prevents data conflicts when a simulation service
        # is reconfigured to start interacting with a controller.
        desc = self.state.desc()

        if desc.connection_kind == 'SIM':
            return f'simulator__{self.config.name}'

        return desc.controller.device.device_id

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

        desc = self.state.desc()

        if desc.firmware_error == 'INCOMPATIBLE':
            raise exceptions.IncompatibleFirmware()

        if desc.identity_error == 'INCOMPATIBLE':
            raise exceptions.InvalidDeviceId()

    @subroutine('sync block store')
    async def _sync_block_store(self):
        await self.block_store.load(self.device_name)

    @subroutine('sync controller settings')
    async def _sync_sysinfo(self):
        await self.set_sysinfo_settings()

    async def set_converter_units(self):
        LOGGER.info('\n'.join(traceback.format_tb(None)))
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
                nid=const.SYSINFO_NID,
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
            await self.connection.reset()

        await self.state.wait_disconnected()

    async def repeat(self):
        try:
            self.settings_store.service_settings_listeners.add(self._apply_service_settings)
            self.settings_store.global_settings_listeners.add(self._apply_global_settings)
            while True:
                await self.run()
        finally:
            self.settings_store.service_settings_listeners.remove(self._apply_service_settings)
            self.settings_store.global_settings_listeners.remove(self._apply_global_settings)


@asynccontextmanager
async def lifespan():
    sync = SparkSynchronization()
    async with utils.task_context(sync.repeat()):
        yield
