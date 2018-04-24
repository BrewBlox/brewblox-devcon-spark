"""
Defines the REST API for the device
"""

from typing import Type, List

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
    except Exception as ex:
        LOGGER.debug(f'REST error: {ex}')
        return web.json_response({'error': str(ex)}, status=500)


class Api():

    def __init__(self, app: web.Application):
        self._ctrl = device.get_controller(app)


class ObjectApi(Api):

    async def create(self, service_id: str, obj_type: int, data: dict) -> dict:
        object = {
            'service_id': service_id,
            'object_type': obj_type,
            'object_data': data
        }

        await self._ctrl.create_object(
            object_type=obj_type,
            object_size=18,  # TODO(Bob): fix protocol
            object_data=data
        )

        # TODO(Bob): get controller id from create object
        controller_id = [1, 2, 3]

        try:
            await self._ctrl.create_alias(
                # service ID already is in object
                controller_id=controller_id,
                **object
            )
        except Exception as ex:
            # TODO(Bob): uncomment when create returns an object
            # await self.delete(id=controller_id)
            raise ex

        return object

    async def read(self, service_id: str, obj_type: int=0) -> dict:
        return await self._ctrl.read_value(
            object_id=service_id,
            object_type=obj_type,
            object_size=0
        )

    async def update(self, service_id: str, obj_type: int, data: dict) -> dict:
        return await self._ctrl.write_value(
            object_id=service_id,
            object_type=obj_type,
            object_size=0,
            object_data=data
        )

    async def delete(self, service_id: str) -> dict:
        return await self._ctrl.delete_object(
            object_id=service_id
        )

    async def all(self) -> dict:
        return await self._ctrl.list_objects(
            profile_id=self._ctrl.active_profile
        )


class SystemApi(Api):

    async def read(self, service_id: str) -> dict:
        return await self._ctrl.read_system_value(
            system_object_id=service_id,
            object_type=0,
            object_size=0
        )

    async def update(self, service_id: str, obj_type: int, data: dict) -> dict:
        return await self._ctrl.write_system_value(
            system_object_id=service_id,
            object_type=obj_type,
            object_size=0,
            object_data=data
        )


class ProfileApi(Api):

    async def create(self) -> dict:
        return await self._ctrl.create_profile()

    async def delete(self, profile_id: int) -> dict:
        return await self._ctrl.delete_profile(
            profile_id=profile_id
        )

    async def activate(self, profile_id: int) -> dict:
        retval = await self._ctrl.activate_profile(
            profile_id=profile_id
        )
        self._ctrl.active_profile = profile_id
        return retval


class AliasApi(Api):

    async def create(self, service_id: str, controller_id: List[int]) -> dict:
        return await self._ctrl.create_alias(
            service_id=service_id,
            controller_id=controller_id
        )

    async def update(self, existing_id: str, new_id: str) -> dict:
        return await self._ctrl.update_alias(existing_id, new_id)


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
                data:
                    type: object
                    example: {"profile_id":0}
    """
    request_args = await request.json()
    command = request_args['command']
    data = request_args['data']
    controller = device.get_controller(request.app)
    func = getattr(controller, command)
    return web.json_response(await func(**data))


@routes.post('/objects')
async def object_create(request: web.Request) -> web.Response:
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
                id:
                    type: string
                    example: temp_sensor_1
                type:
                    type: int
                    example: 2
                data:
                    type: object
                    example: {"command":2, "data":4136}
    """
    request_args = await request.json()

    return web.json_response(
        await ObjectApi(request.app).create(
            request_args['id'],
            request_args['type'],
            request_args['data']
        )
    )


@routes.get('/objects/{id}')
async def object_read(request: web.Request) -> web.Response:
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
    return web.json_response(
        await ObjectApi(request.app).read(
            request.match_info['id']
        )
    )


@routes.put('/objects/{id}')
async def object_update(request: web.Request) -> web.Response:
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
                data:
                    type: object
                    example: {"command":2, "data":4136}
    """
    request_args = await request.json()

    return web.json_response(
        await ObjectApi(request.app).update(
            request.match_info['id'],
            request_args['type'],
            request_args['data'],
        )
    )


@routes.delete('/objects/{id}')
async def object_delete(request: web.Request) -> web.Response:
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
    return web.json_response(
        await ObjectApi(request.app).delete(
            request.match_info['id']
        )
    )


@routes.get('/objects')
async def object_all(request: web.Request) -> web.Response:
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
    return web.json_response(
        await ObjectApi(request.app).all()
    )


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
            request.match_info['id']
        )
    )


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
                data:
                    type: object
                    example: { "command": { "opcode":2, "data":4136 } }
    """
    request_args = await request.json()

    return web.json_response(
        await SystemApi(request.app).update(
            request.match_info['id'],
            request_args['type'],
            request_args['data']
        )
    )


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
    return web.json_response(
        await ProfileApi(request.app).create()
    )


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
    return web.json_response(
        await ProfileApi(request.app).delete(
            int(request.match_info['id'])
        )
    )


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
    return web.json_response(
        await ProfileApi(request.app).activate(
            int(request.match_info['id'])
        )
    )


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
                service_id:
                    type: str
                    example: onewirebus
                    required: true
                controller_id:
                    type: list
                    example: [2]
                    required: true
    """
    request_args = await request.json()

    return web.json_response(
        await AliasApi(request.app).create(
            request_args['service_id'],
            request_args['controller_id']
        )
    )


@routes.put('/aliases/{current_id}')
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
        name: current_id
        in: path
        required: true
        schema:
            type: int
    -
        in: body
        name: body
        description: alias
        required: true
        schema:
            type: object
            properties:
                new_id:
                    type: str
                    example: onewirebus
                    required: true
    """
    return web.json_response(
        await AliasApi(request.app).update(
            request.match_info['current_id'],
            (await request.json())['new_id']
        )
    )
