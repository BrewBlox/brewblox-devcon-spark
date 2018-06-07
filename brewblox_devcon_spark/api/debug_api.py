"""
Debug functionality for the Spark REST API
"""


from aiohttp import web
from brewblox_devcon_spark import device
from brewblox_service import brewblox_logger

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()


def setup(app: web.Application):
    app.middlewares.append(controller_error_middleware)
    app.router.add_routes(routes)


@web.middleware
async def controller_error_middleware(request: web.Request, handler: web.RequestHandler) -> web.Response:
    try:
        return await handler(request)
    except Exception as ex:
        LOGGER.debug(f'REST error: {ex}', exc_info=True)
        return web.json_response({'error': str(ex)}, status=500)


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
                    example: {"profile_id":0}
    """
    request_args = await request.json()

    command = request_args['command']
    data = request_args['data']

    func = getattr(device.get_controller(request.app), command)
    return web.json_response(await func(**data))
