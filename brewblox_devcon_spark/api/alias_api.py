"""
REST API for aliases: the human-readable service ID associated with the controller ID.

Controller IDs are defined by the Spark, and are immutable.
Users are free to change the associated service ID.
"""

import re

from aiohttp import web
from aiohttp_apispec import docs, match_info_schema, request_schema
from brewblox_service import brewblox_logger

from brewblox_devcon_spark import datastore, exceptions
from brewblox_devcon_spark.api import schemas

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
    if next((keys for keys in datastore.SYS_OBJECT_KEYS if sid == keys[0]), None):
        raise exceptions.InvalidId(f'"{sid}" is an ID reserved for a system object')


class AliasApi():

    def __init__(self, app: web.Application):
        self._store = datastore.get_block_store(app)

    async def create(self, sid: str, nid: int) -> dict:
        validate_sid(sid)
        self._store[sid, nid] = dict()

    async def update(self, existing_id: str, new_id: str) -> dict:
        validate_sid(new_id)
        self._store.rename((existing_id, None), (new_id, None))

    async def delete(self, sid: str):
        validate_sid(sid)
        del self._store[sid, None]


@docs(
    tags=['Aliases'],
    summary='Create new block alias',
)
@routes.post('/aliases')
@request_schema(schemas.AliasCreateSchema)
async def alias_create(request: web.Request) -> web.Response:
    data = request['data']
    return web.json_response(
        await AliasApi(request.app).create(data['sid'], data['nid'])
    )


@docs(
    tags=['Aliases'],
    summary='Update existing block alias',
)
@routes.put('/aliases/{id}')
@match_info_schema(schemas.StringIdSchema)
@request_schema(schemas.StringIdSchema)
async def alias_update(request: web.Request) -> web.Response:
    existing = request['match_info']['id']
    desired = request['data']['id']
    return web.json_response(
        await AliasApi(request.app).update(existing, desired)
    )


@docs(
    tags=['Aliases'],
    summary='Delete existing block alias',
)
@routes.delete('/aliases/{id}')
@match_info_schema(schemas.StringIdSchema)
async def alias_delete(request: web.Request) -> web.Response:
    id = request['match_info']['id']
    return web.json_response(
        await AliasApi(request.app).delete(id)
    )
