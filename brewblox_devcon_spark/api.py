"""
Defines the REST API for the device
"""

from aiohttp import web
import logging
from brewblox_devcon_spark import device
from typing import Type

LOGGER = logging.getLogger(__name__)
routes = web.RouteTableDef()


def setup(app: Type[web.Application]):
    app.router.add_routes(routes)


def _parse_id(id: str) -> list:
    return [int(i) for i in id.split('-')]


@routes.post('/_debug/write')
async def write(request: web.Request) -> web.Response:
    """
    ---
    tags:
    - Debug
    operationId: controller.spark.debug.write
    summary: Write a serial command
    description: >
        Writes a raw serial command to the controller.
        Does not return anything.
    produces:
    - application/json
    parameters:
    -
        in: body
        name: body
        description: command
        required: try
        schema:
            type: object
            properties:
                command:
                    type: string
                    example: '0F00'
    """
    command = (await request.json())['command']
    retval = await device.get_controller(request.app).write(command)
    return web.json_response(dict(written=retval))


@routes.post('/_debug/do')
async def do_command(request: web.Request) -> web.Response:
    """
    ---
    tags:
    - Debug
    operationId: controller.spark.debug.do
    summary: Do a specific command
    description: >
        Sends command, and returns controller response.
    produces:
    - application/json
    parameters:
    -
        in: body
        name: body
        description: command
        required: try
        schema:
            type: object
            properties:
                command:
                    type: string
                    example: list_objects
                kwargs:
                    type: object
                    example: {"profile_id":0}
    """
    request_args = await request.json()
    command = request_args['command']
    data = request_args['kwargs']
    controller = device.get_controller(request.app)
    return web.json_response(await controller.do(command, data))


@routes.post('/objects')
async def create(request: web.Request) -> web.Response:
    """
    ---
    tags:
    - Spark
    operationId: controller.spark.objects.create
    produces:
    - application/json
    parameters:
    -
        in: body
        name: body
        description: object
        required: true
        schema:
            type: object
            properties:
                type:
                    type: int
                    example: 2
                obj:
                    type: object
                    example: {"command":2, "data":4136}
    """
    request_args = await request.json()
    controller = device.get_controller(request.app)

    obj_type = request_args['type']
    obj_args = request_args['obj']
    return web.json_response(await controller.create(obj_type, obj_args))


@routes.get('/objects/{id}')
async def read(request: web.Request) -> web.Response:
    """
    ---
    tags:
    - Spark
    operationId: controller.spark.objects.read
    produces:
    - application/json
    parameters:
    -
        name: id
        in: path
        required: true
        description: object ID, separated by -
        schema:
            type: string
    """
    obj_id = [int(i) for i in request.match_info['id'].split('-')]
    controller = device.get_controller(request.app)

    return web.json_response(await controller.read(obj_id))


@routes.put('/objects/{id}')
async def update(request: web.Request) -> web.Response:
    """
    ---
    tags:
    - Spark
    operationId: controller.spark.objects.update
    produces:
    - application/json
    parameters:
    -
        name: id
        in: path
        required: true
        description: object ID, separated by '-'
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
                    type: int
                    example: 2
                obj:
                    type: object
                    example: {"command":2, "data":4136}
    """
    request_args = await request.json()
    controller = device.get_controller(request.app)

    obj_id = _parse_id(request.match_info['id'])
    obj_type = request_args['type']
    obj_args = request_args['obj']

    return web.json_response(await controller.update(obj_id, obj_type, obj_args))


@routes.delete('/objects/{id}')
async def delete(request: web.Request) -> web.Response:
    """
    ---
    tags:
    - Spark
    operationId: controller.spark.objects.delete
    produces:
    - application/json
    parameters:
    -
        name: id
        in: path
        required: true
        description: object ID, separated by '-'
        schema:
            type: string
    """
    obj_id = _parse_id(request.match_info['id'])
    controller = device.get_controller(request.app)

    return web.json_response(await controller.delete(obj_id))


@routes.get('/objects')
async def all(request: web.Request) -> web.Response:
    """
    ---
    tags:
    - Spark
    operationId: controller.spark.objects.all
    produces:
    - application/json
    """
    controller = device.get_controller(request.app)
    return web.json_response(await controller.all())


@routes.get('/system/{id}')
async def system_read(request: web.Request) -> web.Response:
    """
    ---
    tags:
    - Spark
    operationId: controller.spark.system.read
    produces:
    - application/json
    parameters:
    -
        name: id
        in: path
        required: true
        description: object ID, separated by '-'
        schema:
            type: string
    """
    obj_id = _parse_id(request.match_info['id'])
    controller = device.get_controller(request.app)

    return web.json_response(await controller.system_read(obj_id))


@routes.put('/system/{id}')
async def system_update(request: web.Request) -> web.Response:
    """
    ---
    tags:
    - Spark
    operationId: controller.spark.system.update
    produces:
    - application/json
    parameters:
    -
        name: id
        in: path
        required: true
        description: object ID, separated by -
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
                    type: int
                    example: 10
                obj:
                    type: object
                    example: { "command": { "opcode":2, "data":4136 } }
    """
    request_args = await request.json()
    controller = device.get_controller(request.app)

    obj_id = _parse_id(request.match_info['id'])
    obj_type = request_args['type']
    obj_args = request_args['obj']

    return web.json_response(await controller.system_update(obj_id, obj_type, obj_args))
