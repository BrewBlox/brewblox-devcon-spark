"""
Specific endpoints for using system objects
"""

import asyncio
from typing import Awaitable, List

from aiohttp import web
from brewblox_service import brewblox_logger, strex

from brewblox_devcon_spark import commander, device, status, ymodem
from brewblox_devcon_spark.api import API_DATA_KEY, object_api
from brewblox_devcon_spark.datastore import GROUPS_NID

REBOOT_WINDOW_S = 5

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()


def setup(app: web.Application):
    app.router.add_routes(routes)


class SystemApi():

    def __init__(self, app: web.Application):
        self._app = app
        self._obj_api: object_api.ObjectApi = object_api.ObjectApi(app)

    async def read_groups(self) -> Awaitable[List[int]]:
        groups = await self._obj_api.read(GROUPS_NID)
        return groups[API_DATA_KEY]['active']

    async def write_groups(self, groups: List[int]) -> Awaitable[List[int]]:
        group_obj = await self._obj_api.write(
            sid=GROUPS_NID,
            groups=[],
            input_type='Groups',
            input_data={'active': groups}
        )
        return group_obj[API_DATA_KEY]['active']

    async def flash(self) -> Awaitable[dict]:  # pragma: no cover
        address = status.get_status(self._app).address

        if not address or ':' not in address:
            raise ConnectionAbortedError(f'Invalid address {address} (flashing over USB is not yet supported)')

        host = address.split(':')[0]
        port = self._app['config']['firmware_port']

        try:
            LOGGER.info('Starting firmware update')
            await commander.get_commander(self._app).pause()
            await ymodem.FileSender().transfer(host, port)
            LOGGER.info('Firmware updated!')
        except Exception as ex:
            LOGGER.error(f'Failed to update firmware {strex(ex)}')
        finally:
            await asyncio.sleep(REBOOT_WINDOW_S)
            await commander.get_commander(self._app).resume()

        return {'host': host, 'port': port}


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
    _status = status.get_status(request.app)
    return web.json_response(_status.state)


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
        await SystemApi(request.app).flash()
    )
