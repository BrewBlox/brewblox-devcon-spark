"""
Defines the REST API for the device
"""

from typing import List, Type

from aiohttp import web
from brewblox_devcon_spark.device import (CONTROLLER_ID_KEY, OBJECT_DATA_KEY,
                                          OBJECT_ID_KEY, OBJECT_LIST_KEY,
                                          OBJECT_TYPE_KEY, PROFILE_ID_KEY,
                                          SERVICE_ID_KEY, SYSTEM_ID_KEY,
                                          get_controller)
from brewblox_service import brewblox_logger

API_ID_KEY = 'id'
API_TYPE_KEY = 'type'
API_DATA_KEY = 'data'
API_LIST_KEY = 'objects'

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()


def setup(app: Type[web.Application]):
    app.router.add_routes(routes)
    app.middlewares.append(controller_error_middleware)


@web.middleware
async def controller_error_middleware(request: web.Request, handler: web.RequestHandler) -> web.Response:
    try:
        return await handler(request)
    except Exception as ex:
        LOGGER.debug(f'REST error: {ex}', exc_info=True)
        return web.json_response({'error': str(ex)}, status=500)


class Api():

    def __init__(self, app: web.Application):
        self._ctrl = get_controller(app)


class ObjectApi(Api):

    async def create(self, input_id: str, input_type: int, input_data: dict) -> dict:
        """
        Creates a new object on the controller.

        Updates the data store with the newly created object.
        Returns read() output after creation.
        """
        response = await self._ctrl.create_object({
            OBJECT_TYPE_KEY: input_type,
            OBJECT_DATA_KEY: input_data
        })

        created_id = response[OBJECT_ID_KEY]

        try:

            # Update service ID with user-determined service ID
            # Add object type to data store
            await self._ctrl.update_store_object(
                created_id,
                {
                    SERVICE_ID_KEY: input_id,
                    OBJECT_TYPE_KEY: input_type
                }
            )

            # Data store was updated
            # We can now say a new object was created with user-determined ID
            created_id = input_id

        except Exception as ex:
            # Failed to update, we'll stick with auto-assigned ID
            LOGGER.warn(f'Failed to update datastore after create: {ex}')

        return await self.read(created_id)

    async def read(self, input_id: str, input_type: int=0) -> dict:
        """
        Reads object on the controller.

        TODO(Bob): Use the object cache
        """
        response = await self._ctrl.read_value({
            OBJECT_ID_KEY: input_id,
            OBJECT_TYPE_KEY: input_type
        })

        return {
            API_ID_KEY: response[OBJECT_ID_KEY],
            API_TYPE_KEY: response[OBJECT_TYPE_KEY],
            API_DATA_KEY: response[OBJECT_DATA_KEY]
        }

    async def update(self, input_id: str, input_type: int, input_data: dict) -> dict:
        """
        Writes new values to existing object on controller
        """
        response = await self._ctrl.write_value({
            OBJECT_ID_KEY: input_id,
            OBJECT_TYPE_KEY: input_type,
            OBJECT_DATA_KEY: input_data
        })

        return {
            API_ID_KEY: response[OBJECT_ID_KEY],
            API_TYPE_KEY: response[OBJECT_TYPE_KEY],
            API_DATA_KEY: response[OBJECT_DATA_KEY]
        }

    async def delete(self, input_id: str) -> dict:
        """
        Deletes object from controller and data store
        """

        await self._ctrl.delete_object({
            OBJECT_ID_KEY: input_id
        })

        await self._ctrl.delete_store_object(
            input_id
        )

        return {
            API_ID_KEY: input_id
        }

    async def all(self) -> list:
        response = await self._ctrl.list_objects({
            PROFILE_ID_KEY: self._ctrl.active_profile
        })

        return [
            {
                API_ID_KEY: obj[OBJECT_ID_KEY],
                API_TYPE_KEY: obj[OBJECT_TYPE_KEY],
                API_DATA_KEY: obj[OBJECT_DATA_KEY]
            } for obj in response.get(OBJECT_LIST_KEY, [])
        ]

    async def all_data(self) -> dict:
        response = await self._ctrl.list_objects({
            PROFILE_ID_KEY: self._ctrl.active_profile
        })

        return {
            obj[OBJECT_ID_KEY]: obj[OBJECT_DATA_KEY]
            for obj in response.get(OBJECT_LIST_KEY, [])
        }


class SystemApi(Api):

    async def read(self, input_id: str, input_type: int=0) -> dict:
        response = await self._ctrl.read_system_value({
            SYSTEM_ID_KEY: input_id,
            OBJECT_TYPE_KEY: input_type
        })

        return {
            API_ID_KEY: response[SYSTEM_ID_KEY],
            API_TYPE_KEY: response[OBJECT_TYPE_KEY],
            API_DATA_KEY: response[OBJECT_DATA_KEY]
        }

    async def update(self, input_id: str, input_type: int, input_data: dict) -> dict:
        response = await self._ctrl.write_system_value({
            SYSTEM_ID_KEY: input_id,
            OBJECT_TYPE_KEY: input_type,
            OBJECT_DATA_KEY: input_data
        })

        return {
            API_ID_KEY: response[SYSTEM_ID_KEY],
            API_TYPE_KEY: response[OBJECT_TYPE_KEY],
            API_DATA_KEY: response[OBJECT_DATA_KEY]
        }


class ProfileApi(Api):

    async def create(self) -> dict:
        response = await self._ctrl.create_profile()

        return {
            API_ID_KEY: response[PROFILE_ID_KEY]
        }

    async def delete(self, profile_id: int) -> dict:
        await self._ctrl.delete_profile({
            PROFILE_ID_KEY: profile_id
        })

        return {
            API_ID_KEY: profile_id
        }

    async def activate(self, profile_id: int) -> dict:
        await self._ctrl.activate_profile({
            PROFILE_ID_KEY: profile_id
        })
        self._ctrl.active_profile = profile_id

        return {
            API_ID_KEY: profile_id
        }

    async def all(self) -> dict:
        response = await self._ctrl.list_profiles()
        return response


class AliasApi(Api):

    async def create(self, service_id: str, controller_id: List[int]) -> dict:
        return await self._ctrl.create_alias({
            SERVICE_ID_KEY: service_id,
            CONTROLLER_ID_KEY: controller_id
        })

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

    func = getattr(get_controller(request.app), command)
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
            request_args[API_ID_KEY],
            request_args[API_TYPE_KEY],
            request_args[API_DATA_KEY]
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
            request.match_info[API_ID_KEY]
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
            request.match_info[API_ID_KEY],
            request_args[API_TYPE_KEY],
            request_args[API_DATA_KEY],
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
            request.match_info[API_ID_KEY]
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


@routes.get('/data')
async def object_all_data(request: web.Request) -> web.Response:
    """
    ---
    summary: Gets data from all objects
    tags:
    - Spark
    - Objects
    operationId: controller.spark.objects.all_data
    produces:
    - application/json
    """
    return web.json_response(
        await ObjectApi(request.app).all_data()
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
            request.match_info[API_ID_KEY]
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
            request.match_info[API_ID_KEY],
            request_args[API_TYPE_KEY],
            request_args[API_DATA_KEY]
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
            int(request.match_info[API_ID_KEY])
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
            int(request.match_info[API_ID_KEY])
        )
    )


@routes.get('/profiles')
async def profiles_all(request: web.Request) -> web.Response:
    """
    ---
    summary: List all profiles
    tags:
    - Spark
    - Objects
    operationId: controller.spark.profiles.all
    produces:
    - application/json
    """
    return web.json_response(
        await ProfileApi(request.app).all()
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
            request_args[SERVICE_ID_KEY],
            request_args[CONTROLLER_ID_KEY]
        )
    )


@routes.put('/aliases/{id}')
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
        name: id
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
                id:
                    type: str
                    example: onewirebus
                    required: true
    """
    return web.json_response(
        await AliasApi(request.app).update(
            request.match_info[API_ID_KEY],
            (await request.json())[API_ID_KEY]
        )
    )
