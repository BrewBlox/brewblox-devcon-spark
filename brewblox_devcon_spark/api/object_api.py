"""
REST API for Spark objects
"""

import asyncio

from aiohttp import web
from brewblox_service import brewblox_logger

from brewblox_devcon_spark import (datastore, device, exceptions, status,
                                   twinkeydict)
from brewblox_devcon_spark.api import (API_DATA_KEY, API_ID_KEY,
                                       API_INTERFACE_KEY, API_TYPE_KEY,
                                       alias_api, utils)
from brewblox_devcon_spark.device import (OBJECT_DATA_KEY, OBJECT_ID_KEY,
                                          OBJECT_ID_LIST_KEY,
                                          OBJECT_INTERFACE_KEY,
                                          OBJECT_LIST_KEY, OBJECT_TYPE_KEY,
                                          PROFILE_LIST_KEY)

SYNC_WAIT_TIMEOUT_S = 20

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()


def setup(app: web.Application):
    app.router.add_routes(routes)


class ObjectApi():

    def __init__(self, app: web.Application, wait_sync=True):
        self._wait_sync = wait_sync
        self._status = status.get_status(app)
        self._ctrl: device.SparkController = device.get_controller(app)
        self._store: twinkeydict.TwinKeyDict = datastore.get_datastore(app)

    def _as_api_object(self, obj: dict):
        return {
            API_ID_KEY: obj[OBJECT_ID_KEY],
            PROFILE_LIST_KEY: obj[PROFILE_LIST_KEY],
            API_TYPE_KEY: obj[OBJECT_TYPE_KEY],
            API_DATA_KEY: obj[OBJECT_DATA_KEY]
        }

    async def wait_for_sync(self):
        if self._wait_sync and self._status.connected.is_set():
            await asyncio.wait_for(self._status.synchronized.wait(), SYNC_WAIT_TIMEOUT_S)

    async def create(self,
                     input_id: str,
                     profiles: list,
                     input_type: int,
                     input_data: dict
                     ) -> dict:
        """
        Creates a new object in the datastore and controller.
        """
        await self.wait_for_sync()
        alias_api.validate_service_id(input_id)

        try:
            placeholder = object()
            self._store[input_id, placeholder] = 'PLACEHOLDER'
        except twinkeydict.TwinKeyError as ex:
            raise exceptions.ExistingId(ex) from ex

        try:
            created = await self._ctrl.create_object({
                PROFILE_LIST_KEY: profiles,
                OBJECT_TYPE_KEY: input_type,
                OBJECT_DATA_KEY: input_data
            })

        finally:
            del self._store[input_id, placeholder]

        self._store.rename((created[OBJECT_ID_KEY], None), (input_id, None))

        return {
            API_ID_KEY: input_id,
            PROFILE_LIST_KEY: created[PROFILE_LIST_KEY],
            API_TYPE_KEY: created[OBJECT_TYPE_KEY],
            API_DATA_KEY: created[OBJECT_DATA_KEY],
        }

    async def read(self, input_id: str) -> dict:
        await self.wait_for_sync()
        response = await self._ctrl.read_object({
            OBJECT_ID_KEY: input_id
        })
        return self._as_api_object(response)

    async def write(self,
                    input_id: str,
                    profiles: list,
                    input_type: str,
                    input_data: dict
                    ) -> dict:
        """
        Writes new values to existing object on controller
        """
        await self.wait_for_sync()
        response = await self._ctrl.write_object({
            OBJECT_ID_KEY: input_id,
            PROFILE_LIST_KEY: profiles,
            OBJECT_TYPE_KEY: input_type,
            OBJECT_DATA_KEY: input_data
        })
        return self._as_api_object(response)

    async def delete(self, input_id: str) -> dict:
        """
        Deletes object from controller and data store
        """
        await self.wait_for_sync()
        await self._ctrl.delete_object({
            OBJECT_ID_KEY: input_id
        })

        del self._store[input_id, None]

        return {
            API_ID_KEY: input_id
        }

    async def all(self) -> list:
        await self.wait_for_sync()
        response = await self._ctrl.list_objects()
        return [self._as_api_object(obj) for obj in response.get(OBJECT_LIST_KEY, [])]

    async def read_stored(self, input_id: str) -> dict:
        await self.wait_for_sync()
        response = await self._ctrl.read_stored_object({
            OBJECT_ID_KEY: input_id
        })
        return self._as_api_object(response)

    async def all_stored(self) -> dict:
        await self.wait_for_sync()
        response = await self._ctrl.list_stored_objects()
        return [self._as_api_object(obj) for obj in response.get(OBJECT_LIST_KEY, [])]

    async def all_logged(self) -> dict:
        await self.wait_for_sync()
        response = await self._ctrl.log_objects()
        return [self._as_api_object(obj) for obj in response.get(OBJECT_LIST_KEY, [])]

    async def list_compatible(self, interface: str) -> list:
        await self.wait_for_sync()
        response = await self._ctrl.list_compatible_objects({
            OBJECT_INTERFACE_KEY: interface,
        })

        return [obj[OBJECT_ID_KEY] for obj in response[OBJECT_ID_LIST_KEY]]

    async def discover(self) -> list:
        await self.wait_for_sync()
        response = await self._ctrl.discover_objects()
        return [obj[OBJECT_ID_KEY] for obj in response[OBJECT_ID_LIST_KEY]]

    async def clear_objects(self):
        await self.wait_for_sync()
        await self._ctrl.clear_objects()
        self._store.clear()
        return {}

    async def reset_objects(self, objects: list) -> list:
        await self.wait_for_sync()
        await self.clear_objects()
        for obj in objects:
            obj_id = obj[API_ID_KEY]
            obj_profiles = obj[PROFILE_LIST_KEY]
            obj_type = obj[API_TYPE_KEY]
            obj_data = obj[API_DATA_KEY]

            if (obj_id, None) in self._store:
                await self.write(obj_id, obj_profiles, obj_type, obj_data)
            else:
                await self.create(obj_id, obj_profiles, obj_type, obj_data)

        return await self.all()


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
                    type: array
                    example: [0, 3, 4]
                type:
                    type: string
                    example: TempSensorOneWire
                data:
                    type: object
                    example:
                        {
                            "address": "FF",
                            "offset[delta_degF]": 20,
                            "value": 200,
                            "valid": true
                        }
    """
    request_args = await request.json()

    with utils.collecting_input():
        args = (
            request_args[API_ID_KEY],
            request_args[PROFILE_LIST_KEY],
            request_args[API_TYPE_KEY],
            request_args[API_DATA_KEY],
        )

    return web.json_response(
        await ObjectApi(request.app).create(*args)
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
                    example: [0, 4, 8]
                type:
                    type: string
                    example: TempSensorOneWire
                data:
                    type: object
                    example:
                        {
                            "address": "FF",
                            "offset[delta_degF]": 20,
                            "value": 200,
                            "valid": true
                        }
    """
    request_args = await request.json()

    with utils.collecting_input():
        args = (
            request.match_info[API_ID_KEY],
            request_args[PROFILE_LIST_KEY],
            request_args[API_TYPE_KEY],
            request_args[API_DATA_KEY],
        )

    return web.json_response(
        await ObjectApi(request.app).write(*args)
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
async def all_objects(request: web.Request) -> web.Response:
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
        await ObjectApi(request.app).all()
    )


@routes.delete('/objects')
async def clear_objects(request: web.Request) -> web.Response:
    """
    ---
    summary: Clear all objects
    tags:
    - Spark
    - Objects
    operationId: controller.spark.objects.clear
    produces:
    - application/json
    """
    return web.json_response(
        await ObjectApi(request.app).clear_objects()
    )


@routes.get('/stored_objects/{id}')
async def stored_read(request: web.Request) -> web.Response:
    """
    ---
    summary: Read object
    tags:
    - Spark
    - Objects
    operationId: controller.spark.stored.read
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
        await ObjectApi(request.app).read_stored(
            request.match_info[API_ID_KEY]
        )
    )


@routes.get('/stored_objects')
async def all_stored(request: web.Request) -> web.Response:
    """
    ---
    summary: Lists all stored objects
    tags:
    - Spark
    - Objects
    operationId: controller.spark.stored.all
    produces:
    - application/json
    """
    return web.json_response(
        await ObjectApi(request.app).all_stored()
    )


@routes.get('/logged_objects')
async def all_logged(request: web.Request) -> web.Response:
    """
    ---
    summary: Lists all objects, with unlogged data keys stripped
    tags:
    - Spark
    - Objects
    operationId: controller.spark.logged.all
    produces:
    - application/json
    """
    return web.json_response(
        await ObjectApi(request.app).all_logged()
    )


@routes.get('/compatible_objects')
async def all_compatible(request: web.Request) -> web.Response:
    """
    ---
    summary: Returns object IDs for all compatible objects
    tags:
    - Spark
    - Objects
    operationId: controller.spark.compatible.all
    produces:
    - application/json
    parameters:
    -
        in: query
        name: interface
        schema:
            type: string
            example: "SetpointLink"
            required: true
    """
    return web.json_response(
        await ObjectApi(request.app).list_compatible(
            request.query.get(API_INTERFACE_KEY)
        )
    )


@routes.get('/discover_objects')
async def discover(request: web.Request) -> web.Response:
    """
    ---
    summary: Discovers newly connected devices
    tags:
    - Spark
    - Objects
    operationId: controller.spark.discover
    produces:
    - application/json
    """
    return web.json_response(await ObjectApi(request.app).discover())


@routes.post('/reset_objects')
async def reset(request: web.Request) -> web.Response:
    """
    ---
    summary: Delete all blocks on controller, and set to given state
    tags:
    - Spark
    - Objects
    operationId: controller.spark.objects.reset
    produces:
    - application/json
    parameters:
    -
        in: body
        name: body
        description: new objects
        required: true
        schema:
            type: array
            items:
                type: object
                properties:
                    id:
                        type: string
                        example: temp_sensor_1
                    profiles:
                        type: array
                        example: [0, 3, 4]
                    type:
                        type: string
                        example: TempSensorOneWire
                    data:
                        type: object
                        example:
                            {
                                "address": "FF",
                                "offset[delta_degF]": 20,
                                "value": 200,
                                "valid": true
                            }
    """
    return web.json_response(await ObjectApi(request.app).reset_objects(await request.json()))
