"""
Debug functionality for the Spark REST API
"""


from aiohttp import web
from aiohttp_apispec import docs, request_schema
from brewblox_service import brewblox_logger

from brewblox_devcon_spark import device
from brewblox_devcon_spark.api import schemas

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()


def setup(app: web.Application):
    app.router.add_routes(routes)


@docs(
    tags=['Debug'],
    summary='Manually send a Spark controller command',
)
@routes.post('/_debug/do')
@request_schema(schemas.ManualCommandSchema)
async def do_command(request: web.Request) -> web.Response:
    command = request['data']['command']
    data = request['data']['data']

    func = getattr(device.get_device(request.app), command)
    return web.json_response(await func(**data))
