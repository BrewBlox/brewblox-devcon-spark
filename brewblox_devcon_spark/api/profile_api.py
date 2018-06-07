"""
REST API for Spark profiles
"""

from aiohttp import web
from brewblox_devcon_spark.api import API_ID_KEY
from brewblox_devcon_spark.device import PROFILE_ID_KEY, get_controller
from brewblox_service import brewblox_logger

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()


def setup(app: web.Application):
    app.router.add_routes(routes)


class ProfileApi():

    def __init__(self, app: web.Application):
        self._ctrl = get_controller(app)

    async def create(self) -> dict:
        response = await self._ctrl.create_profile()

        return {
            API_ID_KEY: response[PROFILE_ID_KEY]
        }

    async def delete(self, profile_id: int) -> dict:
        await self._ctrl.delete_profile({
            PROFILE_ID_KEY: profile_id
        })

        return {
            API_ID_KEY: profile_id
        }

    async def activate(self, profile_id: int) -> dict:
        await self._ctrl.activate_profile({
            PROFILE_ID_KEY: profile_id
        })

        # Set active profile on the controller
        # This is used by other APIs
        self._ctrl.active_profile = profile_id

        return {
            API_ID_KEY: profile_id
        }

    async def all(self) -> dict:
        response = await self._ctrl.list_profiles()
        return response


@routes.post('/profiles')
async def profile_create(request: web.Request) -> web.Response:
    """
    ---
    summary: Create profile
    tags:
    - Spark
    - Profiles
    operationId: controller.spark.profiles.create
    produces:
    - application/json
    """
    return web.json_response(
        await ProfileApi(request.app).create()
    )


@routes.delete('/profiles/{id}')
async def profile_delete(request: web.Request) -> web.Response:
    """
    ---
    summary: Delete profile
    tags:
    - Spark
    - Profiles
    operationId: controller.spark.profiles.delete
    produces:
    - application/json
    parameters:
    -
        name: id
        in: path
        required: true
        schema:
            type: int
    """
    return web.json_response(
        await ProfileApi(request.app).delete(
            int(request.match_info[API_ID_KEY])
        )
    )


@routes.post('/profiles/{id}')
async def profile_activate(request: web.Request) -> web.Response:
    """
    ---
    summary: Activate profile
    tags:
    - Spark
    - Profiles
    operationId: controller.spark.profiles.activate
    produces:
    - application/json
    parameters:
    -
        name: id
        in: path
        required: true
        schema:
            type: int
    """
    return web.json_response(
        await ProfileApi(request.app).activate(
            int(request.match_info[API_ID_KEY])
        )
    )


@routes.get('/profiles')
async def profiles_all(request: web.Request) -> web.Response:
    """
    ---
    summary: List all profiles
    tags:
    - Spark
    - Objects
    operationId: controller.spark.profiles.all
    produces:
    - application/json
    """
    return web.json_response(
        await ProfileApi(request.app).all()
    )
