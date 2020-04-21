"""
Specific endpoints for using system objects
"""

import asyncio
from typing import List

from aiohttp import web
from brewblox_service import brewblox_logger, events, scheduler, strex

from brewblox_devcon_spark import commander, device, exceptions, state, ymodem
from brewblox_devcon_spark.api import object_api
from brewblox_devcon_spark.datastore import GROUPS_NID
from brewblox_devcon_spark.validation import API_DATA_KEY

TRANSFER_TIMEOUT_S = 30
STATE_TIMEOUT_S = 20
CONNECT_INTERVAL_S = 3
CONNECT_ATTEMPTS = 5

FLUSH_PERIOD_S = 3
REBOOT_WINDOW_S = 5

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()


def setup(app: web.Application):
    app.router.add_routes(routes)


async def shutdown_soon():  # pragma: no cover
    await asyncio.sleep(REBOOT_WINDOW_S)
    raise web.GracefulExit()


class FirmwareUpdater():

    def __init__(self, app: web.Application):
        self.app = app
        self.name = app['config']['name']
        self.simulation = app['config']['simulation']
        self.state_exchange = app['config']['state_exchange']
        self.version = app['ini']['firmware_version']
        self.date = app['ini']['firmware_date']

    def _notify(self, msg: str):
        LOGGER.info(msg)
        asyncio.create_task(
            events.publish(self.app,
                           exchange=self.state_exchange,
                           routing=self.name,
                           message={
                               'key': self.name,
                               'type': 'Spark.update',
                               'ttl': '10s',
                               'data': [msg]
                           }))

    async def _connect(self, address) -> ymodem.Connection:  # pragma: no cover
        for i in range(CONNECT_ATTEMPTS):
            try:
                await asyncio.sleep(CONNECT_INTERVAL_S)
                return await ymodem.connect(address)
            except ConnectionRefusedError:
                LOGGER.debug('Connection refused, retrying...')
        raise ConnectionRefusedError()

    async def flash(self) -> dict:  # pragma: no cover
        sender = ymodem.FileSender(self._notify)
        cmder = commander.get_commander(self.app)
        address = state.summary(self.app).address

        self._notify(f'Started updating {self.name}@{address} to version {self.version} ({self.date})')

        try:
            if not state.summary(self.app).connect:
                self._notify('Controller is not connected. Aborting update.')
                raise exceptions.NotConnected()

            if self.simulation:
                raise NotImplementedError('Firmware updates not available for simulation controllers')

            self._notify('Sending update command to controller')
            await cmder.start_update(FLUSH_PERIOD_S)

            self._notify('Waiting for normal connection to close')
            await asyncio.wait_for(state.wait_disconnect(self.app), STATE_TIMEOUT_S)

            self._notify(f'Connecting to {address}')
            conn = await self._connect(address)

            with conn.autoclose():
                await asyncio.wait_for(sender.transfer(conn), TRANSFER_TIMEOUT_S)

        except Exception as ex:
            self._notify(f'Failed to update firmware: {strex(ex)}')
            raise exceptions.FirmwareUpdateFailed(strex(ex))

        finally:
            self._notify('Scheduling service reboot')
            await scheduler.create(self.app, shutdown_soon())

        self._notify('Firmware updated!')
        return {'address': address, 'version': self.version}


class SystemApi():

    def __init__(self, app: web.Application):
        self.app = app
        self._obj_api: object_api.ObjectApi = object_api.ObjectApi(app)

    async def read_groups(self) -> List[int]:
        groups = await self._obj_api.read(GROUPS_NID)
        return groups[API_DATA_KEY]['active']

    async def write_groups(self, groups: List[int]) -> List[int]:
        group_obj = await self._obj_api.write(
            sid=GROUPS_NID,
            groups=[],
            input_type='Groups',
            input_data={'active': groups}
        )
        return group_obj[API_DATA_KEY]['active']

    async def reboot(self):
        async def wrapper():
            try:
                await device.get_controller(self.app).reboot()
            except exceptions.CommandTimeout:
                pass
            except Exception as ex:  # pragma: no cover
                LOGGER.error(f'Unexpected error in reboot command: {strex(ex)}')
        asyncio.create_task(wrapper())
        return {}

    async def factory_reset(self):
        async def wrapper():
            try:
                await device.get_controller(self.app).factory_reset()
            except exceptions.CommandTimeout:
                pass
            except Exception as ex:  # pragma: no cover
                LOGGER.error(f'Unexpected error in factory reset command: {strex(ex)}')
        asyncio.create_task(wrapper())
        return {}


@routes.get('/system/groups')
async def groups_read(request: web.Request) -> web.Response:
    """
    ---
    summary: Read active groups
    tags:
    - Spark
    - System
    - Groups
    operationId: controller.spark.groups.read
    produces:
    - application/json
    """
    return web.json_response(
        await SystemApi(request.app).read_groups()
    )


@routes.put('/system/groups')
async def groups_write(request: web.Request) -> web.Response:
    """
    ---
    summary: Write active groups
    tags:
    - Spark
    - System
    - Groups
    operationId: controller.spark.groups.write
    produces:
    - application/json
    parameters:
    -
        name: groups
        type: list
        example: [0, 1, 2, 3]
    """
    return web.json_response(
        await SystemApi(request.app).write_groups(await request.json())
    )


@routes.get('/system/status')
async def check_status(request: web.Request) -> web.Response:
    """
    ---
    summary: Get service status
    tags:
    - Spark
    - System
    operationId: controller.spark.system.status
    produces:
    - application/json
    """
    return web.json_response(state.summary_dict(request.app))


@routes.get('/system/ping')
async def ping(request: web.Request) -> web.Response:
    """
    ---
    summary: Ping controller
    tags:
    - Spark
    - System
    operationId: controller.spark.system.ping
    produces:
    - application/json
    """
    return web.json_response(
        await device.get_controller(request.app).noop()
    )


@routes.get('/system/reboot')
async def reboot(request: web.Request) -> web.Response:
    """
    ---
    summary: Reboot controller
    tags:
    - Spark
    - System
    operationId: controller.spark.system.reboot
    produces:
    - application/json
    """
    return web.json_response(
        await SystemApi(request.app).reboot()
    )


@routes.get('/system/factory_reset')
async def factory_reset(request: web.Request) -> web.Response:
    """
    ---
    summary: Factory reset controller
    tags:
    - Spark
    - System
    operationId: controller.spark.system.reset
    produces:
    - application/json
    """
    return web.json_response(
        await SystemApi(request.app).factory_reset()
    )


@routes.post('/system/flash')
async def flash(request: web.Request) -> web.Response:
    """
    ---
    summary: Flash controller
    tags:
    - Spark
    - System
    operationId: controller.spark.system.flash
    produces:
    - application/json
    """
    return web.json_response(
        await FirmwareUpdater(request.app).flash()
    )
