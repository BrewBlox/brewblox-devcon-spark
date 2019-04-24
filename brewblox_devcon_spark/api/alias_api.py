"""
REST API for aliases: the human-readable service ID associated with the controller ID.

Controller IDs are defined by the Spark, and are immutable.
Users are free to change the associated service ID.
"""

import re

from aiohttp import web
from brewblox_service import brewblox_logger

from brewblox_devcon_spark import datastore, exceptions
from brewblox_devcon_spark.api import API_SID_KEY, utils

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()

SERVICE_ID_PATTERN = re.compile(
    r'^[a-z]{1}[^\[\]\<\>]{0,199}$',
    re.IGNORECASE
)
SERVICE_ID_RULES = """
An object ID must adhere to the following rules:
- Starts with a letter
- May not contain brackets: '[]<>'
- At most 200 characters
"""


def setup(app: web.Application):
    app.router.add_routes(routes)


def validate_service_id(id: str):
    if not re.match(SERVICE_ID_PATTERN, id):
        raise exceptions.InvalidId(SERVICE_ID_RULES)
    if next((keys for keys in datastore.SYS_OBJECT_KEYS if id == keys[0]), None):
        raise exceptions.InvalidId(f'"{id}" is an ID reserved for a system object')


class AliasApi():

    def __init__(self, app: web.Application):
        self._store = datastore.get_datastore(app)

    async def create(self, service_id: str, controller_id: int) -> dict:
        validate_service_id(service_id)
        self._store[service_id, controller_id] = dict()

    async def update(self, existing_id: str, new_id: str) -> dict:
        validate_service_id(new_id)
        self._store.rename((existing_id, None), (new_id, None))


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
                    type: int
                    example: 2
                    required: true
    """
    request_args = await request.json()
    with utils.collecting_input():
        args = (
            request_args['service_id'],
            request_args['controller_id'],
        )

    return web.json_response(
        await AliasApi(request.app).create(*args)
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
    with utils.collecting_input():
        args = (
            request.match_info[API_SID_KEY],
            (await request.json())[API_SID_KEY],
        )
    return web.json_response(
        await AliasApi(request.app).update(*args)
    )
