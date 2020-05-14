"""
REST API for Codec configuration
"""

from aiohttp import web
from brewblox_service import brewblox_logger

from brewblox_devcon_spark.codec import codec

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()


def setup(app: web.Application):
    app.router.add_routes(routes)


@routes.get('/codec/units')
async def units_get(request: web.Request) -> web.Response:
    """
    ---
    summary: Get current unit configuration
    tags:
    - Spark
    - Codec
    operationId: controller.spark.codec.units.get
    produces:
    - application/json
    """
    return web.json_response(codec.get_codec(request.app).get_unit_config())


@routes.put('/codec/units')
async def units_put(request: web.Request) -> web.Response:
    """
    ---
    summary: Set base units
    tags:
    - Spark
    - Codec
    operationId: controller.spark.codec.units.put
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
    args = await request.json()
    return web.json_response(codec.get_codec(request.app).update_unit_config(args))
