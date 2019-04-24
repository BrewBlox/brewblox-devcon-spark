"""
Catches Python error, and returns appropriate error codes
"""

import asyncio
import traceback

from aiohttp import web, web_exceptions
from brewblox_service import brewblox_logger

from brewblox_devcon_spark.api.utils import strex
from brewblox_devcon_spark.exceptions import BrewBloxException

LOGGER = brewblox_logger(__name__)


def setup(app: web.Application):
    app.middlewares.append(controller_error_middleware)


def error_response(request: web.Request, ex: Exception, status: int) -> web.Response:
    app = request.app
    message = strex(ex)
    debug = app['config']['debug']
    LOGGER.error(f'[{request.url}] => {message}', exc_info=debug)

    response = {'error': message}

    if debug:
        response['traceback'] = traceback.format_tb(ex.__traceback__)

    return web.json_response(response, status=status)


@web.middleware
async def controller_error_middleware(request: web.Request, handler: web.RequestHandler) -> web.Response:
    try:
        return await handler(request)

    except asyncio.CancelledError:
        raise  # pragma: no cover

    except web_exceptions.HTTPError:
        raise  # pragma: no cover

    except BrewBloxException as ex:
        return error_response(request, ex, status=ex.status_code)

    except Exception as ex:
        return error_response(request, ex, status=500)
