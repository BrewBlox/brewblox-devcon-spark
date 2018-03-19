"""
Defines endpoints and basic functionality for the BrewPi Spark controller
"""

import asyncio
import logging
from typing import Type

from aiohttp import web
from nesdict import NesDict

from brewblox_devcon_spark.commander import SparkCommander

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
        self.commander: SparkCommander = None

        if app:
            self.setup(app)

    def get(self, path: str='*') -> dict:
        return self.state.get(path)

    def setup(self, app: Type[web.Application]):
        app.on_startup.append(self.start)
        app.on_cleanup.append(self.close)

    async def start(self, app: Type[web.Application]):
        self.commander = SparkCommander()
        self.commander.bind(loop=app.loop)

    async def close(self, app):
        if self.commander:
            self.commander.close()

    async def write(self, command: str):
        return await self.commander.conduit.write(command)

    async def do(self, command, *args, **kwargs):
        f = getattr(self.commander, command)
        LOGGER.info(f'command={command}, args={args}, kwargs={kwargs}')
        return await f(*args, **kwargs)


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
    command = (await request.json())['command']
    retval = await get_controller(request.app).write(command)
    return web.json_response(dict(written=retval))


@routes.post('/do')
async def do_command(request: web.Request) -> web.Response:
    """
    ---
    tags:
    - Controller
    - Spark
    operationId: controller.spark.do
    summary: Do a specific command
    description: >
        Sends command, without waiting for response.
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
                    example: list_objects
                args:
                    type: array
                    example: []
                kwargs:
                    type: object
    """
    request_args = await request.json()
    command = request_args['command']
    args = request_args['args']
    kwargs = request_args['kwargs']
    controller = get_controller(request.app)
    return web.json_response(await controller.do(command, *args, **kwargs))


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
