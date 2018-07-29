"""
REST API for Spark objects
"""

from aiohttp import web
from brewblox_service import brewblox_logger

from brewblox_devcon_spark import device, twinkeydict
from brewblox_devcon_spark.api import (API_DATA_KEY, API_ID_KEY, API_TYPE_KEY,
                                       alias_api)
from brewblox_devcon_spark.device import (OBJECT_DATA_KEY, OBJECT_ID_KEY,
                                          OBJECT_LIST_KEY, OBJECT_TYPE_KEY,
                                          PROFILE_LIST_KEY)

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()


def setup(app: web.Application):
    app.router.add_routes(routes)


class ObjectApi():

    def __init__(self, app: web.Application):
        self._ctrl: device.SparkController = device.get_controller(app)
        self._store: twinkeydict.TwinKeyDict = twinkeydict.get_object_store(app)

    async def create(self,
                     input_id: str,
                     profiles: list,
                     input_type: int,
                     input_data: dict
                     ) -> dict:
        """
        Creates a new object on the controller.
        Updates the data store with the newly created object.
        """
        alias_api.validate_service_id(input_id)

        created = await self._ctrl.create_object({
            PROFILE_LIST_KEY: profiles,
            OBJECT_TYPE_KEY: input_type,
            OBJECT_DATA_KEY: input_data
        })

        created_id = created[OBJECT_ID_KEY]

        try:
            # Update service ID with user-determined service ID
            self._store.rename((created_id, None), (input_id, None))

            # Data store was updated
            # We can now say a new object was created with user-determined ID
            created_id = input_id

        except Exception as ex:
            # Failed to update, we'll stick with auto-assigned ID
            LOGGER.warn(f'Failed to update datastore after create: {type(ex).__name__}({ex})')

        return {
            API_ID_KEY: created_id,
            PROFILE_LIST_KEY: created[PROFILE_LIST_KEY],
            API_TYPE_KEY: created[OBJECT_TYPE_KEY],
            API_DATA_KEY: created[OBJECT_DATA_KEY],
        }

    async def read(self, input_id: str) -> dict:
        """
        Reads object on the controller.
        """
        response = await self._ctrl.read_object({
            OBJECT_ID_KEY: input_id
        })

        return {
            API_ID_KEY: response[OBJECT_ID_KEY],
            PROFILE_LIST_KEY: response[PROFILE_LIST_KEY],
            API_TYPE_KEY: response[OBJECT_TYPE_KEY],
            API_DATA_KEY: response[OBJECT_DATA_KEY]
        }

    async def write(self,
                    input_id: str,
                    profiles: list,
                    input_type: str,
                    input_data: dict
                    ) -> dict:
        """
        Writes new values to existing object on controller
        """
        response = await self._ctrl.write_object({
            OBJECT_ID_KEY: input_id,
            PROFILE_LIST_KEY: profiles,
            OBJECT_TYPE_KEY: input_type,
            OBJECT_DATA_KEY: input_data
        })

        return {
            API_ID_KEY: response[OBJECT_ID_KEY],
            PROFILE_LIST_KEY: response[PROFILE_LIST_KEY],
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

        del self._store[input_id, None]

        return {
            API_ID_KEY: input_id
        }

    async def list_active(self) -> list:
        response = await self._ctrl.list_active_objects()

        return [
            {
                API_ID_KEY: obj[OBJECT_ID_KEY],
                PROFILE_LIST_KEY: obj[PROFILE_LIST_KEY],
                API_TYPE_KEY: obj[OBJECT_TYPE_KEY],
                API_DATA_KEY: obj[OBJECT_DATA_KEY]
            } for obj in response.get(OBJECT_LIST_KEY, [])
        ]

    async def list_saved(self) -> dict:
        response = await self._ctrl.list_saved_objects()

        return [
            {
                API_ID_KEY: obj[OBJECT_ID_KEY],
                PROFILE_LIST_KEY: obj[PROFILE_LIST_KEY],
                API_TYPE_KEY: obj[OBJECT_TYPE_KEY],
                API_DATA_KEY: obj[OBJECT_DATA_KEY]
            } for obj in response.get(OBJECT_LIST_KEY, [])
        ]


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
                profiles:
                    type: list
                    example: [1, 3, 4]
                type:
                    type: string
                    example: OneWireTempSensor
                data:
                    type: object
                    example:
                        {
                            "settings": {
                                "address": "FF",
                                "offset[delta_degF]": 20
                            },
                            "state": {
                                "value": 12345,
                                "connected": true
                            }
                        }
    """
    request_args = await request.json()

    return web.json_response(
        await ObjectApi(request.app).create(
            request_args[API_ID_KEY],
            request_args[PROFILE_LIST_KEY],
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
async def object_write(request: web.Request) -> web.Response:
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
                profiles:
                    type: list
                    example: [1, 4, 8]
                type:
                    type: string
                    example: OneWireTempSensor
                data:
                    type: object
                    example: {
                            "settings": {
                                "address": "FF",
                                "offset[delta_degF]": 20
                            }
                        }
    """
    request_args = await request.json()

    return web.json_response(
        await ObjectApi(request.app).write(
            request.match_info[API_ID_KEY],
            request_args[PROFILE_LIST_KEY],
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
async def active_objects(request: web.Request) -> web.Response:
    """
    ---
    summary: List all active objects
    tags:
    - Spark
    - Objects
    operationId: controller.spark.objects.active
    produces:
    - application/json
    """
    return web.json_response(
        await ObjectApi(request.app).list_active()
    )


@routes.get('/saved_objects')
async def saved_objects(request: web.Request) -> web.Response:
    """
    ---
    summary: Lists all saved objects
    tags:
    - Spark
    - Objects
    operationId: controller.spark.objects.saved
    produces:
    - application/json
    """
    return web.json_response(
        await ObjectApi(request.app).list_saved()
    )
