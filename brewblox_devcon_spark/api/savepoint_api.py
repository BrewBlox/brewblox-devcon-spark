"""
Endpoints for using spark state backups
"""


from typing import Awaitable, List

from aiohttp import web
from brewblox_service import brewblox_logger

from brewblox_devcon_spark import datastore
from brewblox_devcon_spark.api import object_api

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()


def setup(app: web.Application):
    app.router.add_routes(routes)


class SavepointApi():

    def __init__(self, app: web.Application):
        self._obj_api: object_api.ObjectApi = object_api.ObjectApi(app)
        self._savepoints: datastore.CouchDBConfig = datastore.get_savepoints(app)

    async def read(self, id: str) -> Awaitable[List[dict]]:
        with self._savepoints.open() as savepoints:
            point = savepoints[id]
        return point

    async def write(self, id: str) -> Awaitable[List[dict]]:
        blocks = await self._obj_api.all_stored()
        with self._savepoints.open() as savepoints:
            savepoints[id] = blocks.copy()
        return blocks

    async def apply(self, id: str) -> Awaitable[List[dict]]:
        with self._savepoints.open() as savepoints:
            blocks = savepoints[id]
        return await self._obj_api.reset_objects(blocks)

    async def all(self) -> Awaitable[str]:
        with self._savepoints.open() as savepoints:
            names = list(savepoints.keys())
        return names

    async def delete(self, id: str) -> Awaitable[dict]:
        with self._savepoints.open() as savepoints:
            del savepoints[id]
        return {}


@routes.get('/savepoints/{id}')
async def read_savepoint(request: web.Request) -> web.Response:
    """
    ---
    summary: Read savepoint
    tags:
    - Spark
    - Savepoints
    operationId: controller.spark.savepoints.read
    produces:
    - application/json
    parameters:
    -
        name: id
        in: path
        required: true
        schema:
            type: string
    """
    return web.json_response(
        await SavepointApi(request.app).read(
            request.match_info['id']
        )
    )


@routes.put('/savepoints/{id}')
async def write_savepoint(request: web.Request) -> web.Response:
    """
    ---
    summary: Write savepoint
    tags:
    - Spark
    - Savepoints
    operationId: controller.spark.savepoints.write
    produces:
    - application/json
    parameters:
    -
        name: id
        in: path
        required: true
        schema:
            type: string
    """
    return web.json_response(
        await SavepointApi(request.app).write(
            request.match_info['id']
        )
    )


@routes.post('/savepoints/{id}')
async def apply_savepoint(request: web.Request) -> web.Response:
    """
    ---
    summary: Apply savepoint
    tags:
    - Spark
    - Savepoints
    operationId: controller.spark.savepoints.apply
    produces:
    - application/json
    parameters:
    -
        name: id
        in: path
        required: true
        schema:
            type: string
    """
    return web.json_response(
        await SavepointApi(request.app).apply(
            request.match_info['id']
        )
    )


@routes.delete('/savepoints/{id}')
async def delete_savepoint(request: web.Request) -> web.Response:
    """
    ---
    summary: Delete savepoint
    tags:
    - Spark
    - Savepoints
    operationId: controller.spark.savepoints.delete
    produces:
    - application/json
    parameters:
    -
        name: id
        in: path
        required: true
        schema:
            type: string
    """
    return web.json_response(
        await SavepointApi(request.app).delete(
            request.match_info['id']
        )
    )


@routes.get('/savepoints')
async def all_savepoints(request: web.Request) -> web.Response:
    """
    ---
    summary: List all savepoint IDs
    tags:
    - Spark
    - Savepoints
    operationId: controller.spark.savepoints.all
    produces:
    - application/json
    """
    return web.json_response(
        await SavepointApi(request.app).all()
    )
