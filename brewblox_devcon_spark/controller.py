"""
Defines endpoints and basic functionality for the BrewPi Spark controller
"""

import asyncio
import logging
from typing import Type

from aiohttp import web
from nesdict import NesDict

from brewblox_devcon_spark.serial_comm import SparkConduit

CONTROLLER_KEY = 'controller.spark'

LOGGER = logging.getLogger(__name__)
routes = web.RouteTableDef()


def get_controller(app) -> 'SparkController':
    return app[CONTROLLER_KEY]


def setup(app: Type[web.Application]):
    app[CONTROLLER_KEY] = SparkController(name=app['config']['name'], app=app)
    app.router.add_routes(routes)


class SparkController():
    def __init__(self, name: str, app=None):
        self.name = name
        self.state = NesDict()
        self._task: Type[asyncio.Task] = None
        self.conduit: SparkConduit = None

        if app:
            self.setup(app)

    def get(self, path: str='*') -> dict:
        return self.state.get(path)

    def setup(self, app: Type[web.Application]):
        app.on_startup.append(self.start)
        app.on_cleanup.append(self.close)

    async def start(self, app: Type[web.Application]):
        self.conduit = SparkConduit()
        # while True:
        #     try:
        self.conduit.bind(loop=app.loop)
        #     break
        # except CancelledError:
        #     return
        # except ValueError:
        #     asyncio.sleep(1, loop=app.loop)

    async def close(self, app):
        if self.conduit:
            self.conduit.close()

    async def write(self, command: str):
        return await self.conduit.write(command)


@routes.post('/write')
async def write(request: web.Request) -> web.Response:
    """
    ---
    tags:
    - Controller
    - Spark
    operationId: controller.spark.write
    summary: Write a serial command
    description: >
        Writes a raw serial command to the controller.
        Does not return anything.
    produces:
    - application/json
    parameters:
    -
        in: body
        name: body
        description: command
        required: try
        schema:
            type: object
            properties:
                command:
                    type: string
                    example: '0F00'
    """
    args = await request.json()
    command = args['command']
    controller = get_controller(request.app)
    retval = await controller.write(command)
    return web.json_response(dict(resp=retval))


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
