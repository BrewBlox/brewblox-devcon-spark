"""
REST API for persistent settings
"""

from aiohttp import web
from aiohttp_apispec import docs, request_schema, response_schema
from brewblox_service import brewblox_logger

from brewblox_devcon_spark import synchronization
from brewblox_devcon_spark.api import schemas

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()


def setup(app: web.Application):
    app.router.add_routes(routes)


@docs(
    tags=['Settings'],
    summary='Get user units',
)
@routes.get('/settings/units')
@response_schema(schemas.UserUnitsSchema)
async def units_get(request: web.Request) -> web.Response:
    syncher = synchronization.get_syncher(request.app)
    return web.json_response(syncher.get_user_units())


@docs(
    tags=['Settings'],
    summary='Set user units',
)
@routes.put('/settings/units')
@request_schema(schemas.UserUnitsSchema)
@response_schema(schemas.UserUnitsSchema)
async def units_put(request: web.Request) -> web.Response:
    syncher = synchronization.get_syncher(request.app)
    updated = await syncher.set_user_units(request['data'])
    return web.json_response(updated)


@docs(
    tags=['Settings'],
    summary='Get autoconnecting flag',
)
@routes.get('/settings/autoconnecting')
@response_schema(schemas.AutoconnectingSchema)
async def autoconnecting_get(request: web.Request) -> web.Response:
    syncher = synchronization.get_syncher(request.app)
    enabled = syncher.get_autoconnecting()
    return web.json_response({'enabled': enabled})


@docs(
    tags=['Settings'],
    summary='Set autoconnecting flag',
)
@routes.put('/settings/autoconnecting')
@request_schema(schemas.AutoconnectingSchema)
@response_schema(schemas.AutoconnectingSchema)
async def autoconnect_put(request: web.Request) -> web.Response:
    syncher = synchronization.get_syncher(request.app)
    enabled = await syncher.set_autoconnecting(request['data']['enabled'])
    return web.json_response({'enabled': enabled})
