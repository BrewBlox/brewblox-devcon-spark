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
                                   service_status, service_store, spark)

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
        global_store.fget(self.app).listeners.add(self.on_units_changed)

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
            - Keep sending a Noop command until 'acknowledged' event is set
            - Check firmware info in handshake for compatibility
            - Abort synchronization if firmware/ID is not compatible
        - Synchronize block store
            - Read controller-specific data in datastore
        - Synchronize controller time
            - Send current abs time to controller block
        - Synchronize controller display unit
            - Send correct unit to controller if mismatched
        - Collect and log controller tracing
            - Write read/resume command to SysInfo
            - Tracing is included in response
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
        _service_store = service_store.fget(self.app)
        _global_store = global_store.fget(self.app)

        await datastore.check_remote(self.app)
        await _service_store.read()
        await _global_store.read()

        await self.set_converter_units()

        with _service_store.open() as config:
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

    @subroutine('sync display settings')
    async def _sync_display(self):
        await self.set_display_units()

    async def on_units_changed(self):
        """Callback invoked by global_store"""
        await self.set_converter_units()
        await self.set_display_units()

    async def set_converter_units(self):
        store = global_store.fget(self.app)
        converter = codec.get_converter(self.app)
        converter.temperature = store.units['temperature']
        LOGGER.info(f'Service temperature set to {converter.temperature}')

    async def set_display_units(self):
        if not service_status.desc(self.app).is_acknowledged:
            return

        store = global_store.fget(self.app)
        controller = spark.fget(self.app)

        display_block = await controller.read_object({
            'nid': const.DISPLAY_SETTINGS_NID
        })

        user_value = store.units['temperature']
        expected = 'TEMP_FAHRENHEIT' if user_value == 'degF' else 'TEMP_CELSIUS'
        block_value = display_block['data']['tempUnit']

        if expected != block_value:
            display_block['data']['tempUnit'] = expected
            await controller.write_object(display_block)
            LOGGER.info(f'Spark display temperature set to {user_value}')

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
