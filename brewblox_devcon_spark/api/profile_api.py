"""
REST API for Spark profiles
"""

from aiohttp import web
from brewblox_service import brewblox_logger

from brewblox_devcon_spark.device import PROFILE_LIST_KEY, get_controller

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()


PROFILE_ID_KEY = None


def setup(app: web.Application):
    app.router.add_routes(routes)


class ProfileApi():

    def __init__(self, app: web.Application):
        self._ctrl = get_controller(app)

    async def read_active(self) -> list:
        result = await self._ctrl.read_active_profiles()
        return result[PROFILE_LIST_KEY]

    async def write_active(self, profiles: list) -> list:
        resp = await self._ctrl.write_active_profiles({
            PROFILE_LIST_KEY: profiles
        })

        return resp[PROFILE_LIST_KEY]


@routes.get('/profiles')
async def read_profiles(request: web.Request) -> web.Response:
    """
    ---
    summary: Get active profiles
    tags:
    - Spark
    - Profiles
    operationId: controller.spark.profiles.read
    produces:
    - application/json
    """
    return web.json_response(
        await ProfileApi(request.app).read_active()
    )


@routes.post('/profiles')
async def write_profiles(request: web.Request) -> web.Response:
    """
    ---
    summary: Set active profiles
    tags:
    - Spark
    - Profiles
    operationId: controller.spark.profiles.write
    produces:
    - application/json
    parameters:
    -
        name: body
        in: body
        required: true
        schema:
            type: list
            example: [1, 5, 8]
    """
    request_args = await request.json()
    return web.json_response(
        await ProfileApi(request.app).write_active(request_args)
    )
