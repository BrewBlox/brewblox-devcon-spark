"""
Defines endpoints and basic functionality for the BrewPi Spark controller
"""

from typing import Type
from aiohttp import web
import logging
from nesdict import NesDict

CONTROLLER_KEY = 'controller.spark'

LOGGER = logging.getLogger(__name__)
routes = web.RouteTableDef()


def get_controller(app) -> 'SparkController':
    return app[CONTROLLER_KEY]


def setup(app: Type[web.Application]):
    app[CONTROLLER_KEY] = SparkController(name=app['config']['name'])
    app.router.add_routes(routes)


class SparkController():
    def __init__(self, name: str):
        self.name = name
        self.state = NesDict()

    def get(self, path: str='*') -> dict:
        return self.state.get(path)


@routes.get('/state')
async def all_values(request: web.Request) -> web.Response:
    """
    ---
    tags:
    - Controller
    - Spark
    operationId: controller.spark.state
    summary: Get the complete state of the controller
    description: >
        Retrieves all values as defined by this controller Protobuf spec.
        This will include settings, volatile state, and mapping.
        Block ID's are those as set by the user.
    produces:
    - application/json
    """
    controller = get_controller(request.app)
    return web.json_response(controller.get())


@routes.get('/state/{path}')
async def specific_values(request: web.Request) -> web.Response:
    """
    ---
    tags:
    - Controller
    - Spark
    operationId: controller.spark.state.path
    summary: Get a subset of the controller state.
    description: >
        Retrieves all values matching the given path.
        Values are returned as defined by the controller Protobuf spec.
        Block ID's are those as set by the user.
    produces:
    - application/json
    parameters:
    -
        name: path
        in: path
        required: true
        description: the /-separated subset specification of desired values.
        schema:
            type: string
    """
    path = request.match_info['path']
    controller = get_controller(request.app)
    return web.json_response(controller.get(path))
