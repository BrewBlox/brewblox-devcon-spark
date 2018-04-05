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


@routes.put('/object')
async def create(request: web.Request) -> web.Response:
    """
    ---
    tags:
    - Spark
    operationId: controller.spark.object.create
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
                obj_type:
                    type: int
                    example: 2
                obj_args:
                    type: object
                    example: {"command":2, "data":4136}
    """
    request_args = await request.json()
    controller = device.get_controller(request.app)

    obj_type = request_args['obj_type']
    obj_args = request_args['obj_args']
    return web.json_response(await controller.create(obj_type, obj_args))


@routes.get('/object/{id}')
async def read(request: web.Request) -> web.Response:
    """
    ---
    tags:
    - Spark
    operationId: controller.spark.object.read
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


@routes.post('/object/{id}')
async def update(request: web.Request) -> web.Response:
    """
    ---
    tags:
    - Spark
    operationId: controller.spark.object.update
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
                obj_type:
                    type: int
                    example: 2
                obj_args:
                    type: object
                    example: {"command":2, "data":4136}
    """
    request_args = await request.json()
    controller = device.get_controller(request.app)

    obj_id = [int(i) for i in request.match_info['id'].split('-')]
    obj_type = request_args['obj_type']
    obj_args = request_args['obj_args']

    return web.json_response(await controller.update(obj_id, obj_type, obj_args))


@routes.delete('/object/{id}')
async def delete(request: web.Request) -> web.Response:
    """
    ---
    tags:
    - Spark
    operationId: controller.spark.object.delete
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
    obj_id = [int(i) for i in request.match_info['id'].split('-')]
    controller = device.get_controller(request.app)

    return web.json_response(await controller.delete(obj_id))


@routes.get('/object')
async def all(request: web.Request) -> web.Response:
    """
    ---
    tags:
    - Spark
    operationId: controller.spark.object.all
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
    obj_id = [int(i) for i in request.match_info['id'].split('-')]
    controller = device.get_controller(request.app)

    return web.json_response(await controller.system_read(obj_id))


@routes.post('/system/{id}')
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
                obj_type:
                    type: int
                    example: 10
                obj_args:
                    type: object
                    example: { "command": { "opcode":2, "data":4136 } }
    """
    request_args = await request.json()
    controller = device.get_controller(request.app)

    obj_id = [int(i) for i in request.match_info['id'].split('-')]
    obj_type = request_args['obj_type']
    obj_args = request_args['obj_args']

    return web.json_response(await controller.system_update(obj_id, obj_type, obj_args))
