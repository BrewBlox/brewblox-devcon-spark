"""
Catches Python error, and returns appropriate error codes
"""


from aiohttp import web
from brewblox_service import brewblox_logger
from brewblox_devcon_spark.datastore import ConflictDetectedError, NotUniqueError

LOGGER = brewblox_logger(__name__)


def setup(app: web.Application):
    app.middlewares.append(controller_error_middleware)


def error_response(app: web.Application, ex: Exception) -> dict:
    message = f'{type(ex).__name__}: {str(ex)}'
    LOGGER.info(message, exc_info=app['config']['debug'])
    return {'error': message}


@web.middleware
async def controller_error_middleware(request: web.Request, handler: web.RequestHandler) -> web.Response:
    try:
        return await handler(request)

    except NotUniqueError as ex:
        return web.json_response(
            error_response(request.app, ex),
            status=409  # Conflict
        )

    except ConflictDetectedError as ex:
        return web.json_response(
            error_response(request.app, ex),
            status=428  # Precondition required (user must resolve conflict)
        )

    except Exception as ex:
        return web.json_response(
            error_response(request.app, ex),
            status=500  # Internal server error
        )
