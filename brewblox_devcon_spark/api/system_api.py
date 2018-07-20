"""
REST API for Spark system objects
"""

from aiohttp import web
from brewblox_service import brewblox_logger

from brewblox_devcon_spark.api import API_DATA_KEY, API_ID_KEY, API_TYPE_KEY
from brewblox_devcon_spark.device import (OBJECT_DATA_KEY, OBJECT_TYPE_KEY,
                                          SYSTEM_ID_KEY, get_controller)

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()


def setup(app: web.Application):
    app.router.add_routes(routes)


class SystemApi():

    def __init__(self, app: web.Application):
        self._ctrl = get_controller(app)

    async def read(self, input_id: str, input_type: int=0) -> dict:
        response = await self._ctrl.read_system_object({
            SYSTEM_ID_KEY: input_id,
            OBJECT_TYPE_KEY: input_type
        })

        return {
            API_ID_KEY: response[SYSTEM_ID_KEY],
            API_TYPE_KEY: response[OBJECT_TYPE_KEY],
            API_DATA_KEY: response[OBJECT_DATA_KEY]
        }

    async def write(self, input_id: str, input_type: int, input_data: dict) -> dict:
        response = await self._ctrl.write_system_object({
            SYSTEM_ID_KEY: input_id,
            OBJECT_TYPE_KEY: input_type,
            OBJECT_DATA_KEY: input_data
        })

        return {
            API_ID_KEY: response[SYSTEM_ID_KEY],
            API_TYPE_KEY: response[OBJECT_TYPE_KEY],
            API_DATA_KEY: response[OBJECT_DATA_KEY]
        }


@routes.get('/system/{id}')
async def system_read(request: web.Request) -> web.Response:
    """
    ---
    summary: Read sytem object
    tags:
    - Spark
    - System
    operationId: controller.spark.system.read
    produces:
    - application/json
    parameters:
    -
        name: id
        in: path
        required: true
        description: Service ID of object
        schema:
            type: string
    """
    return web.json_response(
        await SystemApi(request.app).read(
            request.match_info[API_ID_KEY]
        )
    )


@routes.put('/system/{id}')
async def system_write(request: web.Request) -> web.Response:
    """
    ---
    summary: Update system object
    tags:
    - Spark
    - System
    operationId: controller.spark.system.update
    produces:
    - application/json
    parameters:
    -
        name: id
        in: path
        required: true
        description: Service ID of object
        schema:
            type: string
    -
        name: body
        in: body
        description: object
        required: true
        schema:
            type: object
            properties:
                type:
                    type: string
                    example: OneWireBus
                data:
                    type: object
                    example: { "command": { "opcode":2, "data":4136 } }
    """
    request_args = await request.json()

    return web.json_response(
        await SystemApi(request.app).write(
            request.match_info[API_ID_KEY],
            request_args[API_TYPE_KEY],
            request_args[API_DATA_KEY]
        )
    )
