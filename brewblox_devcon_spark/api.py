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
    - Spark
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
    - Spark
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


@routes.post('/_debug/write_system_value')
async def write_system_value(request: web.Request) -> web.Response:
    """
    ---
    tags:
    - Spark
    operationId: controller.spark.debug.write_system_value
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
        required: true
        schema:
            type: object
            properties:
                obj_id:
                    type: array
                    example: [2]
                obj_type:
                    type: int
                    example: 2
                obj_args:
                    type: object
                    example: {"command":2, "data":4136}

    """
    request_args = await request.json()
    obj_id = request_args['obj_id']
    obj_type = request_args['obj_type']
    obj_args = request_args['obj_args']
    controller = device.get_controller(request.app)
    return web.json_response(await controller.write_system_value(obj_id, obj_type, obj_args))


@routes.get('/state')
async def all_values(request: web.Request) -> web.Response:
    """
    ---
    tags:
    - Spark
    operationId: controller.spark.state
    summary: Get the complete state of the controller
    description: >
        Retrieves all values as defined by this controller Protobuf spec.
        This will include settings, volatile state, and mapping.
        Block ID's are those as set by the user.
    produces:
    - application/json
    """
    controller = device.get_controller(request.app)
    return web.json_response(controller.get())


@routes.get('/state/{path}')
async def specific_values(request: web.Request) -> web.Response:
    """
    ---
    tags:
    - Spark
    operationId: controller.spark.state.path
    summary: Get a subset of the controller state.
    description: >
        Retrieves all values matching the given path.
        Values are returned as defined by the controller Protobuf spec.
        Block ID's are those as set by the user.
    produces:
    - application/json
    parameters:
    -
        name: path
        in: path
        required: true
        description: the /-separated subset specification of desired values.
        schema:
            type: string
    """
    path = request.match_info['path']
    controller = device.get_controller(request.app)
    return web.json_response(controller.get(path))


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
    obj_id = request.match_info['id'].split('-')
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
                    example: 2
                obj_args:
                    type: object
                    example: {"command":2, "data":4136}
    """
    request_args = await request.json()
    controller = device.get_controller(request.app)

    obj_id = request.match_info['id'].split('-')
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
        description: object ID, separated by -
        schema:
            type: string
    """
    obj_id = request.match_info['id'].split('-')
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
