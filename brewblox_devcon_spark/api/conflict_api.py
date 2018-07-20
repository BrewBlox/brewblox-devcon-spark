"""
REST API for resolving ID conflicts in the datastore
"""

from aiohttp import web
from brewblox_service import brewblox_logger

from brewblox_devcon_spark import datastore

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()


def setup(app: web.Application):
    app.router.add_routes(routes)


class ConflictApi():

    def __init__(self, app: web.Application):
        self._store = datastore.get_object_store(app)

    async def get(self) -> dict:
        return await self._store.known_conflicts()

    async def resolve(self, id_key: str, obj: dict):
        await self._store.resolve_conflict(id_key, obj)


@routes.get('/conflicts')
async def conflict_all(request: web.Request) -> web.Response:
    """
    ---
    summary: Get all known conflicts.
    tags:
    - Spark
    - Conflicts
    operationId: controller.spark.conflicts.all
    produces:
    - application/json
    """
    return web.json_response(await ConflictApi(request.app).get())


@routes.post('/conflicts')
async def conflict_resolve(request: web.Request) -> web.Response:
    """
    ---
    summary: Resolve a conflict.
    tags:
    - Spark
    - Conflicts
    operationId: controller.spark.conflicts.resolve
    produces:
    - application/json
    parameters:
    -
        in: body
        name: body
        required: true
        schema:
            type: object
            properties:
                id_key:
                    type: string
                    example: service_id
                data:
                    type: object
                    example: {"service_id": "flappy", "controller_id": 2}
    """
    request_args = await request.json()

    return web.json_response(
        await ConflictApi(request.app).resolve(
            request_args['id_key'],
            request_args['data']
        )
    )
