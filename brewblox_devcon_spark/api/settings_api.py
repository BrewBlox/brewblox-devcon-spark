"""
REST API for persistent settings
"""

from aiohttp import web
from brewblox_service import brewblox_logger

from brewblox_devcon_spark import synchronization

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()


def setup(app: web.Application):
    app.router.add_routes(routes)


@routes.get('/settings/units')
async def units_get(request: web.Request) -> web.Response:
    """
    ---
    summary: Get current unit configuration
    tags:
    - Spark
    - Settings
    operationId: controller.spark.settings.units.get
    produces:
    - application/json
    """
    syncher = synchronization.get_syncher(request.app)
    return web.json_response(syncher.get_user_units())


@routes.put('/settings/units')
async def units_put(request: web.Request) -> web.Response:
    """
    ---
    summary: Set base units
    tags:
    - Spark
    - Settings
    operationId: controller.spark.settings.units.put
    produces:
    - application/json
    parameters:
    -
        in: body
        name: body
        description: unit preferences
        required: true
        schema:
            type: object
            properties:
                Temp:
                    type: string
                    example: degC
    """
    syncher = synchronization.get_syncher(request.app)
    updated = await syncher.set_user_units(await request.json())
    return web.json_response(updated)


@routes.get('/settings/autoconnecting')
async def autoconnecting_get(request: web.Request) -> web.Response:
    """
    ---
    summary: Get autoconnecting flag
    tags:
    - Spark
    - Settings
    operationId: controller.spark.settings.autoconnecting.get
    produces:
    - application/json
    """
    syncher = synchronization.get_syncher(request.app)
    enabled = syncher.get_autoconnecting()
    return web.json_response({'enabled': enabled})


@routes.put('/settings/autoconnecting')
async def autoconnect_put(request: web.Request) -> web.Response:
    """
    ---
    summary: Set autoconnect flag
    tags:
    - Spark
    - Settings
    operationId: controller.spark.settings.autoconnecting.put
    produces:
    - application/json
    parameters:
    -
        in: body
        name: body
        description: arguments
        required: true
        schema:
            type: object
            properties:
                enabled:
                    type: boolean
                    example: true
    """
    syncher = synchronization.get_syncher(request.app)
    args = await request.json()
    enabled = await syncher.set_autoconnecting(args['enabled'])
    return web.json_response({'enabled': enabled})
