"""
Defines the REST API for the device
"""

from typing import Type

from aiohttp import web
from brewblox_devcon_spark import brewblox_logger, device

LOGGER = LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()


def setup(app: Type[web.Application]):
    app.router.add_routes(routes)
    app.middlewares.append(controller_error_middleware)


@web.middleware
async def controller_error_middleware(request: web.Request, handler: web.RequestHandler) -> web.Response:
    try:
        return await handler(request)
    except device.ControllerException as ex:
        return web.json_response({'error': str(ex)}, status=500)


@routes.post('/_debug/write')
async def write(request: web.Request) -> web.Response:
    """
    ---
    summary: Write a serial command
    tags:
    - Debug
    operationId: controller.spark.debug.write
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
    summary: Do a specific command
    tags:
    - Debug
    operationId: controller.spark.debug.do
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
    summary: Create object
    tags:
    - Spark
    - Objects
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
    return web.json_response(await controller.object_create(obj_type, obj_args))


@routes.get('/objects/{id}')
async def read(request: web.Request) -> web.Response:
    """
    ---
    summary: Read object
    tags:
    - Spark
    - Objects
    operationId: controller.spark.objects.read
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
    obj_id = request.match_info['id']
    controller = device.get_controller(request.app)

    return web.json_response(await controller.object_read(obj_id))


@routes.put('/objects/{id}')
async def update(request: web.Request) -> web.Response:
    """
    ---
    summary: Update object
    tags:
    - Spark
    - Objects
    operationId: controller.spark.objects.update
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
                    type: int
                    example: 2
                obj:
                    type: object
                    example: {"command":2, "data":4136}
    """
    request_args = await request.json()
    controller = device.get_controller(request.app)

    obj_id = request.match_info['id']
    obj_type = request_args['type']
    obj_args = request_args['obj']

    return web.json_response(await controller.object_update(obj_id, obj_type, obj_args))


@routes.delete('/objects/{id}')
async def delete(request: web.Request) -> web.Response:
    """
    ---
    summary: Delete object
    tags:
    - Spark
    - Objects
    operationId: controller.spark.objects.delete
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
    obj_id = request.match_info['id']
    controller = device.get_controller(request.app)

    return web.json_response(await controller.object_delete(obj_id))


@routes.get('/objects')
async def all(request: web.Request) -> web.Response:
    """
    ---
    summary: List all objects
    tags:
    - Spark
    - Objects
    operationId: controller.spark.objects.all
    produces:
    - application/json
    """
    controller = device.get_controller(request.app)
    return web.json_response(await controller.object_all())


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
    obj_id = request.match_info['id']
    controller = device.get_controller(request.app)

    return web.json_response(await controller.system_read(obj_id))


@routes.put('/system/{id}')
async def system_update(request: web.Request) -> web.Response:
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
                    type: int
                    example: 10
                obj:
                    type: object
                    example: { "command": { "opcode":2, "data":4136 } }
    """
    request_args = await request.json()
    controller = device.get_controller(request.app)

    obj_id = request.match_info['id']
    obj_type = request_args['type']
    obj_args = request_args['obj']

    return web.json_response(await controller.system_update(obj_id, obj_type, obj_args))


@routes.post('/profiles')
async def profile_create(request: web.Request) -> web.Response:
    """
    ---
    summary: Create profile
    tags:
    - Spark
    - Profiles
    operationId: controller.spark.profiles.create
    produces:
    - application/json
    """
    controller = device.get_controller(request.app)
    return web.json_response(await controller.profile_create())


@routes.delete('/profiles/{id}')
async def profile_delete(request: web.Request) -> web.Response:
    """
    ---
    summary: Delete profile
    tags:
    - Spark
    - Profiles
    operationId: controller.spark.profiles.delete
    produces:
    - application/json
    parameters:
    -
        name: id
        in: path
        required: true
        schema:
            type: int
    """
    obj_id = int(request.match_info['id'])
    controller = device.get_controller(request.app)
    return web.json_response(await controller.profile_delete(obj_id))


@routes.post('/profiles/{id}')
async def profile_activate(request: web.Request) -> web.Response:
    """
    ---
    summary: Activate profile
    tags:
    - Spark
    - Profiles
    operationId: controller.spark.profiles.activate
    produces:
    - application/json
    parameters:
    -
        name: id
        in: path
        required: true
        schema:
            type: int
    """
    obj_id = int(request.match_info['id'])
    controller = device.get_controller(request.app)
    return web.json_response(await controller.profile_activate(obj_id))


@routes.post('/aliases')
async def alias_create(request: web.Request) -> web.Response:
    """
    ---
    summary: Create new alias
    tags:
    - Spark
    - Aliases
    operationId: controller.spark.aliases.create
    produces:
    - application/json
    parameters:
    -
        in: body
        name: body
        description: alias
        required: true
        schema:
            type: object
            properties:
                alias:
                    type: str
                    example: onewirebus
                    required: true
                controller_id:
                    type: list
                    example: [2]
                    required: true
    """
    request_args = await request.json()

    controller = device.get_controller(request.app)
    resp = await controller.alias_create(request_args['alias'], request_args['controller_id'])
    return web.json_response(resp)


@routes.put('/aliases/{alias}')
async def alias_update(request: web.Request) -> web.Response:
    """
    ---
    summary: Update existing alias
    tags:
    - Spark
    - Aliases
    operationId: controller.spark.aliases.update
    produces:
    - application/json
    parameters:
    -
        in: body
        name: body
        description: alias
        required: true
        schema:
            type: object
            properties:
                alias:
                    type: str
                    example: onewirebus
                    required: true
    """
    existing = request.match_info['alias']
    new = (await request.json())['alias']

    controller = device.get_controller(request.app)
    resp = await controller.alias_update(existing, new)
    return web.json_response(resp)
