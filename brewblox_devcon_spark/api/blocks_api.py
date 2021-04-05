"""
REST API for Spark blocks
"""

import asyncio
import re
from copy import deepcopy
from typing import List

from aiohttp import web
from aiohttp_apispec import docs, request_schema, response_schema
from brewblox_service import brewblox_logger, mqtt, strex

from brewblox_devcon_spark import (block_cache, block_store, const, exceptions,
                                   service_status, spark, twinkeydict)
from brewblox_devcon_spark.api import schemas

SYNC_WAIT_TIMEOUT_S = 20

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()

SID_PATTERN = re.compile(r'^[a-zA-Z]{1}[a-zA-Z0-9 _\-\(\)\|]{0,199}$')
SID_RULES = """
An object ID must adhere to the following rules:
- Starts with a letter
- May only contain alphanumeric characters, space, and _-()|
- At most 200 characters
"""


def setup(app: web.Application):
    app.router.add_routes(routes)


def validate_sid(sid: str):
    if not re.match(SID_PATTERN, sid):
        raise exceptions.InvalidId(SID_RULES)
    if next((keys for keys in const.SYS_OBJECT_KEYS if sid == keys[0]), None):
        raise exceptions.InvalidId(f'"{sid}" is an ID reserved for system objects')


def merge(a: dict, b: dict):
    """Merges dict b into dict a"""
    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                merge(a[key], b[key])
            else:
                a[key] = b[key]
        else:
            a[key] = b[key]
    return a


class BlocksApi():

    def __init__(self, app: web.Application):
        self.app = app
        self._spark = spark.fget(app)
        self._store = block_store.fget(app)
        self._publish_changed = True

    async def wait_for_sync(self):
        await asyncio.wait_for(
            service_status.wait_synchronized(self.app),
            SYNC_WAIT_TIMEOUT_S)

    async def create(self, block: dict) -> dict:
        """
        Creates a new object in the datastore and controller.
        """
        await self.wait_for_sync()
        # sid is required for new blocks
        sid = block.pop('id')
        validate_sid(sid)

        try:
            placeholder = object()
            self._store[sid, placeholder] = 'PLACEHOLDER'
        except twinkeydict.TwinKeyError as ex:
            raise exceptions.ExistingId(ex) from ex

        try:
            created = await self._spark.create_object(block)

        finally:
            del self._store[sid, placeholder]

        self._store.rename((created['id'], None), (sid, None))
        created['id'] = sid

        block_cache.set(self.app, created)
        await self.publish(changed=[created])
        return created

    async def read(self, ids: dict) -> dict:
        await self.wait_for_sync()
        block = await self._spark.read_object(ids)
        block_cache.set(self.app, block)
        return block

    async def read_logged(self, ids: dict) -> dict:
        await self.wait_for_sync()
        return await self._spark.read_logged_object(ids)

    async def read_stored(self, ids: dict) -> dict:
        await self.wait_for_sync()
        return await self._spark.read_stored_object(ids)

    async def write(self, block: dict) -> dict:
        await self.wait_for_sync()
        block = await self._spark.write_object(block)
        block_cache.set(self.app, block)
        await self.publish(changed=[block])
        return block

    async def patch(self, partial: dict) -> dict:
        await self.wait_for_sync()
        block = block_cache.get(self.app, partial) or await self.read(partial)
        block = deepcopy(block)
        merge(block['data'], partial['data'])
        return await self.write(block)

    async def publish(self, changed: List[dict] = None, deleted: List[str] = None):
        if self._publish_changed:
            name = self.app['config']['name']
            topic = self.app['config']['state_topic'] + f'/{name}/patch'
            await mqtt.publish(self.app,
                               topic,
                               err=False,
                               message={
                                   'key': name,
                                   'type': 'Spark.patch',
                                   'ttl': '1d',
                                   'data': {
                                       'changed': changed or [],
                                       'deleted': deleted or [],
                                   }
                               })

    async def delete(self, ids: dict) -> dict:
        """
        Deletes object from controller and data store
        """
        await self.wait_for_sync()
        sid = ids.get('id')
        nid = ids.get('nid')

        await self._spark.delete_object(ids)

        if sid is None:
            sid = self._store.left_key(nid)
        if nid is None:
            nid = self._store.right_key(sid)

        del self._store[sid, nid]
        ids = {'id': sid, 'nid': nid}
        block_cache.delete(self.app, ids)
        await self.publish(deleted=[sid])
        return ids

    async def read_all(self) -> list:
        await self.wait_for_sync()
        response = await self._spark.list_objects()
        blocks = response.get('objects', [])
        block_cache.set_all(self.app, blocks)
        return blocks

    async def read_all_logged(self) -> list:
        await self.wait_for_sync()
        response = await self._spark.list_logged_objects()
        return response.get('objects', [])

    async def read_all_stored(self) -> list:
        await self.wait_for_sync()
        response = await self._spark.list_stored_objects()
        return response.get('objects', [])

    async def delete_all(self) -> dict:
        await self.wait_for_sync()
        await self._spark.clear_objects()
        self._store.clear()
        await self._spark.write_object({
            'nid': const.DISPLAY_SETTINGS_NID,
            'type': 'DisplaySettings',
            'groups': [],
            'data': {},
        })
        ids = [sid for (sid, nid) in block_cache.keys(self.app)
               if nid >= const.USER_NID_START]
        block_cache.delete_all(self.app)
        await self.publish(deleted=ids)
        return {}

    async def compatible(self, interface: str) -> list:
        await self.wait_for_sync()
        response = await self._spark.list_compatible_objects({
            'interface': interface,
        })
        return response.get('object_ids', [])

    async def discover(self) -> list:
        await self.wait_for_sync()
        response = await self._spark.discover_objects()
        return response.get('objects', [])

    async def validate(self, partial: dict) -> dict:
        return await self._spark.validate(partial)

    async def rename(self, existing: str, desired: str):
        validate_sid(desired)
        self._store.rename((existing, None), (desired, None))
        block_cache.rename(self.app, existing, desired)
        return {
            'id': desired,
            'nid': self._store.right_key(desired),
        }

    async def cleanup(self) -> list:
        await self.wait_for_sync()
        actual = [block['id']
                  for block in await self.read_all()]
        unused = [(sid, nid)
                  for (sid, nid) in self._store
                  if sid not in actual]
        for (sid, nid) in unused.copy():
            del self._store[sid, nid]
        return [{'id': sid, 'nid': nid}
                for (sid, nid) in unused]

    async def backup_save(self) -> dict:
        await self.wait_for_sync()
        store_data = [
            {'keys': keys, 'data': content}
            for keys, content in self._store.items()
        ]
        blocks_data = await self.read_all_stored()
        return {
            'blocks': [
                block for block in blocks_data
                if block['nid'] != const.SYSTIME_NID
            ],
            'store': store_data,
        }

    async def backup_load(self, exported: dict) -> list:
        await self.wait_for_sync()
        await self.delete_all()

        self._publish_changed = False
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
        for block in exported['blocks']:
            try:
                nid = block.get('nid')
                if nid is not None and nid < const.USER_NID_START:
                    await self.write(deepcopy(block))
                else:
                    # Bypass BlockApi.create(), to avoid meddling with store IDs
                    await self._spark.create_object(deepcopy(block))
            except asyncio.CancelledError:  # pragma: no cover
                raise
            except Exception as ex:
                message = f'failed to import block. Error={strex(ex)}, block={block}'
                error_log.append(message)
                LOGGER.error(message)

        self._publish_changed = True
        used_nids = [b.get('nid') for b in await self.read_all()]
        unused = [
            (sid, nid) for (sid, nid) in self._store
            if nid >= const.USER_NID_START
            and nid not in used_nids
        ]
        for sid, nid in unused:
            del self._store[sid, nid]
            message = f'Removed unused alias [{sid},{nid}]'
            LOGGER.info(message)
            error_log.append(message)

        return {'messages': error_log}


@docs(
    tags=['Blocks'],
    summary='Create new block',
)
@routes.post('/blocks/create')
@request_schema(schemas.BlockSchema)
@response_schema(schemas.BlockSchema, 201)
async def _create(request: web.Request) -> web.Response:
    return web.json_response(
        await BlocksApi(request.app).create(request['data']),
        status=201
    )


@docs(
    tags=['Blocks'],
    summary='Read block',
)
@routes.post('/blocks/read')
@request_schema(schemas.BlockIdSchema)
@response_schema(schemas.BlockSchema)
async def _read(request: web.Request) -> web.Response:
    return web.json_response(
        await BlocksApi(request.app).read(request['data'])
    )


@docs(
    tags=['Blocks'],
    summary='Read block. Data only includes logged fields.',
)
@routes.post('/blocks/read/logged')
@request_schema(schemas.BlockIdSchema)
@response_schema(schemas.BlockSchema)
async def _read_logged(request: web.Request) -> web.Response:
    return web.json_response(
        await BlocksApi(request.app).read_logged(request['data'])
    )


@docs(
    tags=['Blocks'],
    summary='Read block',
)
@routes.post('/blocks/read/stored')
@request_schema(schemas.BlockIdSchema)
@response_schema(schemas.BlockSchema)
async def _read_stored(request: web.Request) -> web.Response:
    return web.json_response(
        await BlocksApi(request.app).read_stored(request['data'])
    )


@docs(
    tags=['Blocks'],
    summary='Update existing block',
)
@routes.post('/blocks/write')
@request_schema(schemas.BlockSchema)
@response_schema(schemas.BlockSchema)
async def _write(request: web.Request) -> web.Response:
    return web.json_response(
        await BlocksApi(request.app).write(request['data'])
    )


@docs(
    tags=['Blocks'],
    summary='Patch existing block',
)
@routes.post('/blocks/patch')
@request_schema(schemas.BlockPatchSchema)
@response_schema(schemas.BlockSchema)
async def _patch(request: web.Request) -> web.Response:
    return web.json_response(
        await BlocksApi(request.app).patch(request['data'])
    )


@docs(
    tags=['Blocks'],
    summary='Delete block',
)
@routes.post('/blocks/delete')
@request_schema(schemas.BlockIdSchema(unknown='exclude'))
@response_schema(schemas.BlockIdSchema)
async def _delete(request: web.Request) -> web.Response:
    return web.json_response(
        await BlocksApi(request.app).delete(request['data'])
    )


@docs(
    tags=['Blocks'],
    summary='Get all blocks',
)
@routes.post('/blocks/all/read')
@response_schema(schemas.BlockSchema(many=True))
async def _all_read(request: web.Request) -> web.Response:
    return web.json_response(
        await BlocksApi(request.app).read_all()
    )


@docs(
    tags=['Blocks'],
    summary='Get all blocks. Only include logged data.',
)
@routes.post('/blocks/all/read/logged')
@response_schema(schemas.BlockSchema(many=True))
async def _all_read_logged(request: web.Request) -> web.Response:
    return web.json_response(
        await BlocksApi(request.app).read_all_logged()
    )


@docs(
    tags=['Blocks'],
    summary='Get all blocks. Only include stored data.',
)
@routes.post('/blocks/all/read/stored')
@response_schema(schemas.BlockSchema(many=True))
async def _all_read_stored(request: web.Request) -> web.Response:
    return web.json_response(
        await BlocksApi(request.app).read_all_stored()
    )


@docs(
    tags=['Blocks'],
    summary='Delete all user blocks',
)
@routes.post('/blocks/all/delete')
async def _all_delete(request: web.Request) -> web.Response:
    return web.json_response(
        await BlocksApi(request.app).delete_all()
    )


@docs(
    tags=['Blocks'],
    summary='Clean unused block IDs',
)
@routes.post('/blocks/cleanup')
@response_schema(schemas.BlockIdSchema(many=True))
async def _cleanup(request: web.Request) -> web.Response:
    return web.json_response(
        await BlocksApi(request.app).cleanup()
    )


@docs(
    tags=['Blocks'],
    summary='Rename existing block',
)
@routes.post('/blocks/rename')
@request_schema(schemas.BlockRenameSchema)
@response_schema(schemas.BlockIdSchema)
async def _rename(request: web.Request) -> web.Response:
    return web.json_response(
        await BlocksApi(request.app).rename(**request['data'])
    )


@docs(
    tags=['Blocks'],
    summary='Get IDs for all blocks compatible with interface',
)
@routes.post('/blocks/compatible')
@request_schema(schemas.InterfaceIdSchema)
@response_schema(schemas.BlockIdSchema(many=True))
async def _compatible(request: web.Request) -> web.Response:
    return web.json_response(
        await BlocksApi(request.app).compatible(**request['data'])
    )


@docs(
    tags=['Blocks'],
    summary='Discover newly connected OneWire devices',
)
@routes.post('/blocks/discover')
@response_schema(schemas.BlockSchema(many=True))
async def _discover(request: web.Request) -> web.Response:
    return web.json_response(
        await BlocksApi(request.app).discover()
    )


@docs(
    tags=['Blocks'],
    summary='Validate block data',
)
@routes.post('/blocks/validate')
@request_schema(schemas.BlockValidateSchema)
async def _validate(request: web.Request) -> web.Response:
    return web.json_response(
        await BlocksApi(request.app).validate(request['data'])
    )


@docs(
    tags=['Blocks'],
    summary='Export service blocks to portable format',
)
@routes.post('/blocks/backup/save')
@response_schema(schemas.SparkExportSchema)
async def _backup_save(request: web.Request) -> web.Response:
    return web.json_response(
        await BlocksApi(request.app).backup_save()
    )


@docs(
    tags=['Blocks'],
    summary='Import service blocks from portable format',
)
@routes.post('/blocks/backup/load')
@request_schema(schemas.SparkExportSchema)
async def _backup_load(request: web.Request) -> web.Response:
    return web.json_response(
        await BlocksApi(request.app).backup_load(request['data'])
    )
