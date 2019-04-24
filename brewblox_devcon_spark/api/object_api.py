"""
REST API for Spark objects
"""

import asyncio
from typing import Awaitable

from aiohttp import web
from brewblox_service import brewblox_logger

from brewblox_devcon_spark import (datastore, device, exceptions, status,
                                   twinkeydict)
from brewblox_devcon_spark.api import (API_DATA_KEY, API_INTERFACE_KEY,
                                       API_NID_KEY, API_SID_KEY, API_TYPE_KEY,
                                       alias_api, utils)
from brewblox_devcon_spark.device import (GROUP_LIST_KEY, OBJECT_DATA_KEY,
                                          OBJECT_ID_LIST_KEY,
                                          OBJECT_INTERFACE_KEY,
                                          OBJECT_LIST_KEY, OBJECT_NID_KEY,
                                          OBJECT_SID_KEY, OBJECT_TYPE_KEY)

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
            API_SID_KEY: obj[OBJECT_SID_KEY],
            API_NID_KEY: obj[OBJECT_NID_KEY],
            GROUP_LIST_KEY: obj[GROUP_LIST_KEY],
            API_TYPE_KEY: obj[OBJECT_TYPE_KEY],
            API_DATA_KEY: obj[OBJECT_DATA_KEY]
        }

    async def wait_for_sync(self):
        if self._wait_sync and self._status.connected.is_set():
            await asyncio.wait_for(self._status.synchronized.wait(), SYNC_WAIT_TIMEOUT_S)

    async def create(self,
                     sid: str,
                     groups: list,
                     input_type: int,
                     input_data: dict
                     ) -> Awaitable[dict]:
        """
        Creates a new object in the datastore and controller.
        """
        await self.wait_for_sync()
        alias_api.validate_service_id(sid)

        try:
            placeholder = object()
            self._store[sid, placeholder] = 'PLACEHOLDER'
        except twinkeydict.TwinKeyError as ex:
            raise exceptions.ExistingId(ex) from ex

        try:
            created = await self._ctrl.create_object({
                GROUP_LIST_KEY: groups,
                OBJECT_TYPE_KEY: input_type,
                OBJECT_DATA_KEY: input_data
            })

        finally:
            del self._store[sid, placeholder]

        self._store.rename((created[OBJECT_SID_KEY], None), (sid, None))

        return {
            API_SID_KEY: sid,
            GROUP_LIST_KEY: created[GROUP_LIST_KEY],
            API_TYPE_KEY: created[OBJECT_TYPE_KEY],
            API_DATA_KEY: created[OBJECT_DATA_KEY],
        }

    async def read(self, sid: str) -> Awaitable[dict]:
        await self.wait_for_sync()
        response = await self._ctrl.read_object({
            OBJECT_SID_KEY: sid
        })
        return self._as_api_object(response)

    async def write(self,
                    sid: str,
                    groups: list,
                    input_type: str,
                    input_data: dict
                    ) -> Awaitable[dict]:
        """
        Writes new values to existing object on controller
        """
        await self.wait_for_sync()
        response = await self._ctrl.write_object({
            OBJECT_SID_KEY: sid,
            GROUP_LIST_KEY: groups,
            OBJECT_TYPE_KEY: input_type,
            OBJECT_DATA_KEY: input_data
        })
        return self._as_api_object(response)

    async def delete(self, sid: str) -> Awaitable[dict]:
        """
        Deletes object from controller and data store
        """
        await self.wait_for_sync()
        await self._ctrl.delete_object({
            OBJECT_SID_KEY: sid
        })

        del self._store[sid, None]

        return {
            API_SID_KEY: sid
        }

    async def all(self) -> Awaitable[list]:
        await self.wait_for_sync()
        response = await self._ctrl.list_objects()
        return [self._as_api_object(obj) for obj in response.get(OBJECT_LIST_KEY, [])]

    async def read_stored(self, sid: str) -> Awaitable[dict]:
        await self.wait_for_sync()
        response = await self._ctrl.read_stored_object({
            OBJECT_SID_KEY: sid
        })
        return self._as_api_object(response)

    async def all_stored(self) -> Awaitable[dict]:
        await self.wait_for_sync()
        response = await self._ctrl.list_stored_objects()
        return [self._as_api_object(obj) for obj in response.get(OBJECT_LIST_KEY, [])]

    async def all_logged(self) -> Awaitable[dict]:
        await self.wait_for_sync()
        response = await self._ctrl.log_objects()
        return [self._as_api_object(obj) for obj in response.get(OBJECT_LIST_KEY, [])]

    async def list_compatible(self, interface: str) -> Awaitable[list]:
        await self.wait_for_sync()
        response = await self._ctrl.list_compatible_objects({
            OBJECT_INTERFACE_KEY: interface,
        })

        return [obj[OBJECT_SID_KEY] for obj in response[OBJECT_ID_LIST_KEY]]

    async def discover(self) -> Awaitable[list]:
        await self.wait_for_sync()
        response = await self._ctrl.discover_objects()
        return [obj[OBJECT_SID_KEY] for obj in response[OBJECT_LIST_KEY]]

    async def clear_objects(self) -> Awaitable[dict]:
        await self.wait_for_sync()
        await self._ctrl.clear_objects()
        self._store.clear()
        return {}

    async def export_objects(self) -> Awaitable[dict]:
        await self.wait_for_sync()
        store_data = [
            {'keys': keys, 'data': content}
            for keys, content in self._store.items()
        ]
        blocks_data = await self.all_stored()
        return {
            'blocks': [
                block for block in blocks_data
                if block[API_NID_KEY] != datastore.SYSTIME_NID
            ],
            'store': store_data,
        }

    async def import_objects(self, exported: dict) -> Awaitable[list]:

        async def reset_create(sid: str, groups: list, input_type: str, input_data: dict):
            await self._ctrl.create_object({
                OBJECT_SID_KEY: sid,
                GROUP_LIST_KEY: groups,
                OBJECT_TYPE_KEY: input_type,
                OBJECT_DATA_KEY: input_data
            })

        await self.wait_for_sync()
        await self.clear_objects()

        error_log = []

        # First populate the datastore, to avoid unknown links
        for entry in exported['store']:
            keys = entry['keys']
            data = entry['data']

            try:
                self._store[keys] = data
            except twinkeydict.TwinKeyError:
                sid, nid = keys
                self._store.rename((None, nid), (sid, None))
                self._store[keys] = data

        # Now either create or write the objects, depending on whether they are system objects
        for obj in exported['blocks']:
            obj_sid = obj[API_SID_KEY]
            obj_nid = obj[API_NID_KEY]
            obj_groups = obj[GROUP_LIST_KEY]
            obj_type = obj[API_TYPE_KEY]
            obj_data = obj[API_DATA_KEY]

            func = self.write if obj_nid < datastore.OBJECT_NID_START else reset_create

            try:
                await func(obj_sid, obj_groups, obj_type, obj_data)
            except Exception as ex:
                message = f'failed to import [{obj_sid},{obj_nid},{obj_type}] with {utils.strex(ex)}'
                error_log.append(message)
                LOGGER.error(message)

        return error_log


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
                groups:
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
                            "value": 200
                        }
    """
    request_args = await request.json()

    with utils.collecting_input():
        args = (
            request_args[API_SID_KEY],
            request_args[GROUP_LIST_KEY],
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
            request.match_info[API_SID_KEY]
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
                groups:
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
                            "value": 200
                        }
    """
    request_args = await request.json()

    with utils.collecting_input():
        args = (
            request.match_info[API_SID_KEY],
            request_args[GROUP_LIST_KEY],
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
            request.match_info[API_SID_KEY]
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
            request.match_info[API_SID_KEY]
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
            example: "ProcessValueInterface"
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


@routes.get('/export_objects')
async def export_objects(request: web.Request) -> web.Response:
    """
    ---
    summary: Lists all objects and metadata
    tags:
    - Spark
    - Objects
    operationId: controller.spark.export
    produces:
    - application/json
    """
    return web.json_response(
        await ObjectApi(request.app).export_objects()
    )


@routes.post('/import_objects')
async def import_objects(request: web.Request) -> web.Response:
    """
    ---
    summary: Delete all blocks on controller, and set to given state
    tags:
    - Spark
    - Objects
    operationId: controller.spark.import
    produces:
    - application/json
    parameters:
    -
        in: body
        name: body
        description: exported data
        required: true
    """
    return web.json_response(await ObjectApi(request.app).import_objects(await request.json()))
