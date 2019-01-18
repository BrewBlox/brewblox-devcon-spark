"""
Debug functionality for the Spark REST API
"""


from aiohttp import web
from brewblox_service import brewblox_logger

from brewblox_devcon_spark import device

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()


def setup(app: web.Application):
    app.router.add_routes(routes)


@routes.post('/_debug/do')
async def do_command(request: web.Request) -> web.Response:
    """
    ---
    summary: Do a specific command
    tags:
    - Debug
    operationId: controller.spark.debug.do
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
                data:
                    type: object
                    example: {"group_id":0}
    """
    request_args = await request.json()

    command = request_args['command']
    data = request_args['data']

    func = getattr(device.get_controller(request.app), command)
    return web.json_response(await func(**data))
