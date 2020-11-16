"""
Regulates actions that should be taken when the service connects to a controller.
"""


import asyncio
from datetime import datetime, timedelta
from functools import wraps

from aiohttp import web
from brewblox_service import brewblox_logger, features, repeater, strex

from brewblox_devcon_spark import (block_store, codec, commander, config_store,
                                   const, datastore, exceptions,
                                   service_status, spark)
from brewblox_devcon_spark.exceptions import InvalidInput

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
            except asyncio.CancelledError:  # pragma: no cover
                raise
            except Exception as ex:
                LOGGER.error(f'Sync subroutine failed: {desc} - {strex(ex)}')
                raise ex
        return wrapped
    return wrapper


class SparkSynchronization(repeater.RepeaterFeature):

    async def before_shutdown(self, app: web.Application):
        await self.end()

    async def prepare(self):
        """Implements RepeaterFeature.prepare"""
        pass

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
            - Wait for 'connected' event to be set by connection.py
        - Synchronize handshake
            - Keep sending a Noop command until 'acknowledged' event is set
            - Check firmware info in handshake for compatibility
            - Abort synchronization if firmware/ID is not compatible
        - Synchronize block store
            - Read controller-specific data in datastore.
        - Synchronize controller time
            - Send current abs time to controller block
        - Collect and log controller tracing
            - Write read/resume command to SysInfo
            - Tracing is included in response
        - Set 'synchronized' event
        - Wait for 'disconnected' event

        Implements RepeaterFeature.run
        """
        try:
            await self._sync_service_store()

            await service_status.wait_connected(self.app)
            await self._sync_handshake()
            await self._sync_block_store()
            await self._sync_time()
            await self._collect_call_trace()

            service_status.set_synchronized(self.app)
            LOGGER.info('Service synchronized!')

        except asyncio.CancelledError:
            raise

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

    def get_user_units(self):
        return codec.get_converter(self.app).user_units

    async def set_user_units(self, units):
        converter = codec.get_converter(self.app)
        try:
            converter.user_units = units
            with config_store.fget(self.app).open() as config:
                config[UNIT_CONFIG_KEY] = converter.user_units
        except InvalidInput as ex:
            LOGGER.warn(f'Discarding user units due to error: {strex(ex)}')
        return converter.user_units

    def get_autoconnecting(self):
        return service_status.desc(self.app).is_autoconnecting

    async def set_autoconnecting(self, enabled):
        enabled = bool(enabled)
        service_status.set_autoconnecting(self.app, enabled)
        with config_store.fget(self.app).open() as config:
            config[AUTOCONNECTING_KEY] = enabled
        return enabled

    async def _apply_service_config(self, config):
        converter = codec.get_converter(self.app)
        enabled = config.get(AUTOCONNECTING_KEY, True)
        service_status.set_autoconnecting(self.app, enabled)
        config[AUTOCONNECTING_KEY] = enabled

        units = config.get(UNIT_CONFIG_KEY, {})
        converter.user_units = units
        config[UNIT_CONFIG_KEY] = converter.user_units

    @subroutine('sync service store')
    async def _sync_service_store(self):
        store = config_store.fget(self.app)

        await datastore.check_remote(self.app)
        await store.read()

        with store.open() as config:
            await self._apply_service_config(config)

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
                    await spark.fget(self.app).noop()
                except asyncio.CancelledError:
                    raise
                except Exception:
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
        store = block_store.fget(self.app)
        await datastore.check_remote(self.app)
        await store.read(self.device_name)

    @subroutine('sync controller time')
    async def _sync_time(self):
        now = datetime.now()
        ticks_block = await spark.fget(self.app).write_object({
            'nid': const.SYSTIME_NID,
            'groups': [const.SYSTEM_GROUP],
            'type': 'Ticks',
            'data': {
                'secondsSinceEpoch': now.timestamp()
            }
        })
        ms = ticks_block['data']['millisSinceBoot']
        uptime = timedelta(milliseconds=ms)
        LOGGER.info(f'System uptime: {uptime}')

    async def format_trace(self, src):
        cdc = codec.fget(self.app)
        store = block_store.fget(self.app)
        dest = []
        for src_v in src:
            action = src_v['action']
            nid = src_v['id']
            sid = store.left_key(nid, 'Unknown')
            typename = await cdc.decode(src_v['type'])

            if nid == 0:
                dest.append(action)
            else:
                dest.append(f'{action.ljust(20)} {typename.ljust(20)} [{sid},{nid}]')

        return dest

    @subroutine('collect controller call trace')
    async def _collect_call_trace(self):
        sys_block = await spark.fget(self.app).write_object({
            'nid': const.SYSINFO_NID,
            'groups': [const.SYSTEM_GROUP],
            'type': 'SysInfo',
            'data': {
                'command': 'SYS_CMD_TRACE_READ_RESUME'
            }
        })
        trace = '\n'.join(await self.format_trace(sys_block['data']['trace']))
        LOGGER.info(f'System trace: \n{trace}')


def setup(app: web.Application):
    features.add(app, SparkSynchronization(app))


def fget(app: web.Application) -> SparkSynchronization:
    return features.get(app, SparkSynchronization)
