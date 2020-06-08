"""
REST API for Spark objects
"""

import asyncio

from aiohttp import web
from aiohttp_apispec import (docs, match_info_schema, querystring_schema,
                             request_schema, response_schema)
from brewblox_service import brewblox_logger, strex

from brewblox_devcon_spark import (datastore, device, exceptions, state,
                                   twinkeydict)
from brewblox_devcon_spark.api import alias_api, schemas
from brewblox_devcon_spark.const import (API_DATA_KEY, API_INTERFACE_KEY,
                                         API_NID_KEY, API_SID_KEY,
                                         API_TYPE_KEY, GROUP_LIST_KEY,
                                         OBJECT_DATA_KEY, OBJECT_ID_LIST_KEY,
                                         OBJECT_INTERFACE_KEY, OBJECT_LIST_KEY,
                                         OBJECT_NID_KEY, OBJECT_SID_KEY,
                                         OBJECT_TYPE_KEY)

SYNC_WAIT_TIMEOUT_S = 20

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()


def setup(app: web.Application):
    app.router.add_routes(routes)


class ObjectApi():

    def __init__(self, app: web.Application, wait_sync=True):
        self.app = app
        self._wait_sync = wait_sync
        self._ctrl: device.SparkController = device.get_controller(app)
        self._store: twinkeydict.TwinKeyDict = datastore.get_block_store(app)

    def _as_api_object(self, obj: dict):
        return {
            API_SID_KEY: obj[OBJECT_SID_KEY],
            API_NID_KEY: obj[OBJECT_NID_KEY],
            GROUP_LIST_KEY: obj[GROUP_LIST_KEY],
            API_TYPE_KEY: obj[OBJECT_TYPE_KEY],
            API_DATA_KEY: obj[OBJECT_DATA_KEY]
        }

    async def wait_for_sync(self):
        await asyncio.wait_for(state.wait_synchronize(self.app, self._wait_sync), SYNC_WAIT_TIMEOUT_S)

    async def create(self,
                     sid: str,
                     nid: int,
                     groups: list,
                     input_type: int,
                     input_data: dict
                     ) -> dict:
        """
        Creates a new object in the datastore and controller.
        """
        await self.wait_for_sync()
        alias_api.validate_sid(sid)

        try:
            placeholder = object()
            self._store[sid, placeholder] = 'PLACEHOLDER'
        except twinkeydict.TwinKeyError as ex:
            raise exceptions.ExistingId(ex) from ex

        try:
            created = await self._ctrl.create_object({
                OBJECT_NID_KEY: nid,
                GROUP_LIST_KEY: groups,
                OBJECT_TYPE_KEY: input_type,
                OBJECT_DATA_KEY: input_data
            })

        finally:
            del self._store[sid, placeholder]

        self._store.rename((created[OBJECT_SID_KEY], None), (sid, None))

        return {
            API_SID_KEY: sid,
            API_NID_KEY: self._store.right_key(sid),
            GROUP_LIST_KEY: created[GROUP_LIST_KEY],
            API_TYPE_KEY: created[OBJECT_TYPE_KEY],
            API_DATA_KEY: created[OBJECT_DATA_KEY],
        }

    async def read(self, sid: str) -> dict:
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
                    ) -> dict:
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

    async def delete(self, sid: str) -> dict:
        """
        Deletes object from controller and data store
        """
        await self.wait_for_sync()
        await self._ctrl.delete_object({
            OBJECT_SID_KEY: sid
        })

        # Allow for the endpoint being called with the NID
        if sid.isdigit():
            del self._store[None, int(sid)]
        else:
            del self._store[sid, None]

        return {
            API_SID_KEY: sid
        }

    async def all(self) -> list:
        await self.wait_for_sync()
        response = await self._ctrl.list_objects()
        return [self._as_api_object(obj)
                for obj in response.get(OBJECT_LIST_KEY, [])]

    async def read_stored(self, sid: str) -> dict:
        await self.wait_for_sync()
        response = await self._ctrl.read_stored_object({
            OBJECT_SID_KEY: sid
        })
        return self._as_api_object(response)

    async def all_stored(self) -> list:
        await self.wait_for_sync()
        response = await self._ctrl.list_stored_objects()
        return [self._as_api_object(obj)
                for obj in response.get(OBJECT_LIST_KEY, [])]

    async def all_logged(self) -> list:
        await self.wait_for_sync()
        response = await self._ctrl.log_objects()
        return [self._as_api_object(obj)
                for obj in response.get(OBJECT_LIST_KEY, [])]

    async def list_compatible(self, interface: str) -> list:
        await self.wait_for_sync()
        response = await self._ctrl.list_compatible_objects({
            OBJECT_INTERFACE_KEY: interface,
        })

        return [{API_SID_KEY: obj[OBJECT_SID_KEY]}
                for obj in response[OBJECT_ID_LIST_KEY]]

    async def discover(self) -> list:
        await self.wait_for_sync()
        response = await self._ctrl.discover_objects()
        return [{API_SID_KEY: obj[OBJECT_SID_KEY]}
                for obj in response[OBJECT_LIST_KEY]]

    async def validate(self,
                       input_type: str,
                       input_data: dict) -> dict:
        response = await self._ctrl.validate({
            OBJECT_TYPE_KEY: input_type,
            OBJECT_DATA_KEY: input_data
        })
        return {
            API_TYPE_KEY: response[OBJECT_TYPE_KEY],
            API_DATA_KEY: response[OBJECT_DATA_KEY]
        }

    async def clear_objects(self) -> dict:
        await self.wait_for_sync()
        await self._ctrl.clear_objects()
        self._store.clear()
        await self._ctrl.write_object({
            OBJECT_NID_KEY: datastore.DISPLAY_SETTINGS_NID,
            GROUP_LIST_KEY: [],
            OBJECT_TYPE_KEY: 'DisplaySettings',
            OBJECT_DATA_KEY: {},
        })
        return {}

    async def cleanup_names(self) -> list:
        await self.wait_for_sync()
        actual = [obj[API_SID_KEY] for obj in await self.all()]
        unused = [sid for (sid, nid) in self._store if sid not in actual]
        for sid in unused:
            del self._store[sid, None]
        return unused

    async def export_objects(self) -> dict:
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

    async def import_objects(self, exported: dict) -> list:

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
            except asyncio.CancelledError:  # pragma: no cover
                raise
            except Exception as ex:
                message = f'failed to import [{obj_sid},{obj_nid},{obj_type}] with {strex(ex)}'
                error_log.append(message)
                LOGGER.error(message)

        used_nids = [b.get(API_NID_KEY) for b in await self.all()]
        unused = [
            (sid, nid) for (sid, nid) in self._store
            if nid >= datastore.OBJECT_NID_START
            and nid not in used_nids
        ]
        for sid, nid in unused:
            del self._store[sid, nid]
            message = f'Removed unused alias [{sid},{nid}]'
            LOGGER.info(message)
            error_log.append(message)

        return error_log


@docs(
    tags=['Blocks'],
    summary='Create new block',
)
@routes.post('/objects')
@request_schema(schemas.BlockSchema)
@response_schema(schemas.BlockSchema, 200)
async def object_create(request: web.Request) -> web.Response:
    data = request['data']

    return web.json_response(
        await ObjectApi(request.app).create(
            data[API_SID_KEY],
            data.get(API_NID_KEY),
            data[GROUP_LIST_KEY],
            data[API_TYPE_KEY],
            data[API_DATA_KEY],
        )
    )


@docs(
    tags=['Blocks'],
    summary='Read block',
)
@routes.get('/objects/{id}')
@match_info_schema(schemas.StringIdSchema)
@response_schema(schemas.BlockSchema, 200)
async def object_read(request: web.Request) -> web.Response:
    return web.json_response(
        await ObjectApi(request.app).read(
            request.match_info[API_SID_KEY]
        )
    )


@docs(
    tags=['Blocks'],
    summary='Write block',
)
@routes.put('/objects/{id}')
@match_info_schema(schemas.StringIdSchema)
@request_schema(schemas.BlockSchema)
@response_schema(schemas.BlockSchema, 200)
async def object_write(request: web.Request) -> web.Response:
    data = request['data']
    return web.json_response(
        await ObjectApi(request.app).write(
            request.match_info[API_SID_KEY],
            data[GROUP_LIST_KEY],
            data[API_TYPE_KEY],
            data[API_DATA_KEY],
        )
    )


@docs(
    tags=['Blocks'],
    summary='Delete block',
)
@routes.delete('/objects/{id}')
@match_info_schema(schemas.StringIdSchema)
async def object_delete(request: web.Request) -> web.Response:
    return web.json_response(
        await ObjectApi(request.app).delete(
            request.match_info[API_SID_KEY]
        )
    )


@docs(
    tags=['Blocks'],
    summary='Get all blocks',
)
@routes.get('/objects')
@response_schema(schemas.BlockSchema(many=True), 200)
async def all_objects(request: web.Request) -> web.Response:
    return web.json_response(
        await ObjectApi(request.app).all()
    )


@docs(
    tags=['Blocks'],
    summary='Delete all user blocks',
)
@routes.delete('/objects')
async def clear_objects(request: web.Request) -> web.Response:
    return web.json_response(
        await ObjectApi(request.app).clear_objects()
    )


@docs(
    tags=['Blocks'],
    summary='Clean unused block string IDs',
)
@routes.delete('/unused_names')
async def cleanup_names(request: web.Request) -> web.Response:
    return web.json_response(
        await ObjectApi(request.app).cleanup_names()
    )


@docs(
    tags=['Blocks'],
    summary='Get persistent data for a block',
)
@routes.get('/stored_objects/{id}')
@match_info_schema(schemas.StringIdSchema)
@response_schema(schemas.BlockSchema, 200)
async def stored_read(request: web.Request) -> web.Response:

    return web.json_response(
        await ObjectApi(request.app).read_stored(
            request.match_info[API_SID_KEY]
        )
    )


@docs(
    tags=['Blocks'],
    summary='Get persistent data for all blocks',
)
@routes.get('/stored_objects')
@response_schema(schemas.BlockSchema(many=True), 200)
async def all_stored(request: web.Request) -> web.Response:
    return web.json_response(
        await ObjectApi(request.app).all_stored()
    )


@docs(
    tags=['Blocks'],
    summary='Get logged data for all blocks',
)
@routes.get('/logged_objects')
@response_schema(schemas.BlockSchema(many=True), 200)
async def all_logged(request: web.Request) -> web.Response:
    return web.json_response(
        await ObjectApi(request.app).all_logged()
    )


@docs(
    tags=['Blocks'],
    summary='Get IDs for all blocks compatible with interface',
)
@routes.get('/compatible_objects')
@querystring_schema(schemas.InterfaceIdSchema)
@response_schema(schemas.BlockIdSchema(many=True))
async def all_compatible(request: web.Request) -> web.Response:
    return web.json_response(
        await ObjectApi(request.app).list_compatible(
            request.query.get(API_INTERFACE_KEY)
        )
    )


@docs(
    tags=['Blocks'],
    summary='Discover newly connected OneWire devices',
)
@routes.get('/discover_objects')
@response_schema(schemas.BlockIdSchema(many=True))
async def discover(request: web.Request) -> web.Response:
    return web.json_response(await ObjectApi(request.app).discover())


@docs(
    tags=['Blocks'],
    summary='Validate block data',
)
@routes.post('/validate_object')
@request_schema(schemas.BlockValidateSchema)
async def validate(request: web.Request) -> web.Response:
    data = request['data']
    return web.json_response(
        await ObjectApi(request.app).validate(
            data[API_TYPE_KEY],
            data[API_DATA_KEY]
        )
    )


@docs(
    tags=['Blocks'],
    summary='Export service blocks to portable format',
)
@routes.get('/export_objects')
@response_schema(schemas.SparkExportSchema)
async def export_objects(request: web.Request) -> web.Response:
    return web.json_response(
        await ObjectApi(request.app).export_objects()
    )


@docs(
    tags=['Blocks'],
    summary='Import service blocks from portable format',
)
@routes.post('/import_objects')
@request_schema(schemas.SparkExportSchema)
async def import_objects(request: web.Request) -> web.Response:
    data = request['data']
    return web.json_response(
        await ObjectApi(request.app).import_objects(data)
    )
