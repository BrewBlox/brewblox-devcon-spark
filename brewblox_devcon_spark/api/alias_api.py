"""
REST API for aliases: the human-readable service ID associated with the controller ID.

Controller IDs are defined by the Spark, and are immutable.
Users are free to change the associated service ID.
"""

from typing import List

from aiohttp import web
from brewblox_devcon_spark import datastore
from brewblox_devcon_spark.api import API_ID_KEY
from brewblox_devcon_spark.device import CONTROLLER_ID_KEY, SERVICE_ID_KEY
from brewblox_service import brewblox_logger

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()


def setup(app: web.Application):
    app.router.add_routes(routes)


class AliasApi():

    def __init__(self, app: web.Application):
        self._store = datastore.get_object_store(app)

    async def create(self, service_id: str, controller_id: List[int]) -> dict:
        await self._store.insert_unique(
            id_key=SERVICE_ID_KEY,
            obj={
                SERVICE_ID_KEY: service_id,
                CONTROLLER_ID_KEY: controller_id
            }
        )

    async def update(self, existing_id: str, new_id: str) -> dict:
        await self._store.update_unique(
            id_key=SERVICE_ID_KEY,
            id_val=existing_id,
            obj={SERVICE_ID_KEY: new_id}
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
