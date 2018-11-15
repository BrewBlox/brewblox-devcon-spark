"""
Specific endpoints for using system objects
"""


from typing import List

from aiohttp import web
from brewblox_service import brewblox_logger

from brewblox_devcon_spark.api import API_DATA_KEY, object_api

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()


def setup(app: web.Application):
    app.router.add_routes(routes)


class SystemApi():

    def __init__(self, app: web.Application):
        self._obj_api: object_api.ObjectApi = object_api.ObjectApi(app)

    async def read_profiles(self) -> List[int]:
        profiles = await self._obj_api.read('__profiles')
        return profiles[API_DATA_KEY]['active']

    async def write_profiles(self, profiles: List[int]) -> List[int]:
        profile_obj = await self._obj_api.write(
            input_id='__profiles',
            profiles=[],
            input_type='Profiles',
            input_data={'active': profiles}
        )
        return profile_obj[API_DATA_KEY]['active']


@routes.get('/system/profiles')
async def profiles_read(request: web.Request) -> web.Response:
    """
    ---
    summary: Read active profiles
    tags:
    - Spark
    - System
    - Profiles
    operationId: controller.spark.profiles.read
    produces:
    - application/json
    """
    return web.json_response(
        await SystemApi(request.app).read_profiles()
    )


@routes.put('/system/profiles')
async def profiles_write(request: web.Request) -> web.Response:
    """
    ---
    summary: Write active profiles
    tags:
    - Spark
    - System
    - Profiles
    operationId: controller.spark.profiles.write
    produces:
    - application/json
    parameters:
    -
        name: profiles
        type: list
        example: [0, 1, 2, 3]
    """
    return web.json_response(
        await SystemApi(request.app).write_profiles(await request.json())
    )
