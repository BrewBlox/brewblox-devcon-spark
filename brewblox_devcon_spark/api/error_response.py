"""
Catches Python error, and returns appropriate error codes
"""

import json
import traceback

from aiohttp import web
from brewblox_service import brewblox_logger, strex

from brewblox_devcon_spark.exceptions import BrewbloxException

LOGGER = logging.getLogger(__name__)


def setup(app: web.Application):
    app.middlewares.append(controller_error_middleware)


@web.middleware
async def controller_error_middleware(request: web.Request, handler) -> web.Response:
    try:
        return await handler(request)

    except web.HTTPError:  # pragma: no cover
        raise

    except Exception as ex:
        app = request.app
        message = strex(ex)
        debug = app['config'].debug
        LOGGER.error(f'[{request.url}] => {message}', exc_info=debug)

        response = {'error': message}

        if debug:
            response['traceback'] = traceback.format_tb(ex.__traceback__)

        if isinstance(ex, BrewbloxException):
            http_error = ex.http_error
        else:  # pragma: no cover
            http_error = web.HTTPInternalServerError

        raise http_error(text=json.dumps(response),
                         content_type='application/json')
