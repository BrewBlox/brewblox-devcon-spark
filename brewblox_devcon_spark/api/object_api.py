"""
REST API for Spark objects
"""

from aiohttp import web
from brewblox_devcon_spark import datastore, device
from brewblox_devcon_spark.api import API_DATA_KEY, API_ID_KEY, API_TYPE_KEY
from brewblox_devcon_spark.device import (OBJECT_DATA_KEY, OBJECT_ID_KEY,
                                          OBJECT_LIST_KEY, OBJECT_TYPE_KEY,
                                          PROFILE_ID_KEY, SERVICE_ID_KEY)
from brewblox_service import brewblox_logger

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()


def setup(app: web.Application):
    app.router.add_routes(routes)


class ObjectApi():

    def __init__(self, app: web.Application):
        self._ctrl = device.get_controller(app)
        self._store = datastore.get_object_store(app)

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
            await self._store.update_unique(
                id_key=SERVICE_ID_KEY,
                id_val=created_id,
                obj={
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

        await self._store.delete(
            id_key=SERVICE_ID_KEY,
            id_val=input_id
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
                    example: 6
                data:
                    type: object
                    example:
                        {
                            "settings": {
                                "address": "FF",
                                "offset": 0
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
