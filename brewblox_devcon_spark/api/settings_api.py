"""
REST API for persistent settings
"""

from aiohttp import web
from aiohttp_apispec import docs, json_schema, response_schema
from brewblox_service import brewblox_logger

from brewblox_devcon_spark import synchronization
from brewblox_devcon_spark.api import schemas

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()


def setup(app: web.Application):
    app.router.add_routes(routes)


@docs(
    tags=['Settings'],
    summary='Get autoconnecting flag',
)
@routes.get('/settings/autoconnecting')
@response_schema(schemas.AutoconnectingSchema)
async def autoconnecting_get(request: web.Request) -> web.Response:
    syncher = synchronization.fget(request.app)
    enabled = syncher.get_autoconnecting()
    return web.json_response({'enabled': enabled})


@docs(
    tags=['Settings'],
    summary='Set autoconnecting flag',
)
@routes.put('/settings/autoconnecting')
@json_schema(schemas.AutoconnectingSchema)
@response_schema(schemas.AutoconnectingSchema)
async def autoconnect_put(request: web.Request) -> web.Response:
    syncher = synchronization.fget(request.app)
    enabled = await syncher.set_autoconnecting(request['json']['enabled'])
    return web.json_response({'enabled': enabled})
