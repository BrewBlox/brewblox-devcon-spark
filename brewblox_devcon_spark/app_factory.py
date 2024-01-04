import logging
import traceback
from contextlib import AsyncExitStack, asynccontextmanager
from pprint import pformat

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.responses import JSONResponse

from . import (block_backup, broadcast, codec, command, connection, control,
               datastore_blocks, datastore_settings, mqtt, state_machine,
               synchronization, time_sync, utils)
from .api import (backup_api, blocks_api, blocks_mqtt_api, debug_api,
                  settings_api, sim_api, system_api)
from .models import ErrorResponse

LOGGER = logging.getLogger(__name__)


def setup_logging(debug: bool, trace: bool):
    level = logging.DEBUG if debug else logging.INFO
    unimportant_level = logging.INFO if debug else logging.WARN
    format = '%(asctime)s.%(msecs)03d [%(levelname).1s:%(name)s:%(lineno)d] %(message)s'
    datefmt = '%Y/%m/%d %H:%M:%S'

    logging.basicConfig(level=level, format=format, datefmt=datefmt)
    logging.captureWarnings(True)

    # Enables LOGGER.trace(msg) calls
    # Trace logs are independent from debug logs
    # You can enable either, neither, or both
    utils.add_logging_level('TRACE', level + 5 if trace else level - 5)

    logging.getLogger('gmqtt').setLevel(unimportant_level)
    logging.getLogger('httpx').setLevel(unimportant_level)
    logging.getLogger('httpcore').setLevel(logging.WARN)
    logging.getLogger('uvicorn.access').setLevel(unimportant_level)
    logging.getLogger('uvicorn.error').disabled = True


def add_exception_handlers(app: FastAPI):
    config = utils.get_config()
    logger = logging.getLogger('devcon.error')

    @app.exception_handler(HTTPException)
    async def on_http_error(request: Request, ex: HTTPException) -> JSONResponse:
        msg = str(ex)
        content = ErrorResponse(error=msg)

        if config.debug:
            content.traceback = traceback.format_exception(None, ex, ex.__traceback__)

        logger.error(f'[{request.url}] => {msg}', exc_info=config.debug)
        return JSONResponse(content.model_dump(mode='json', exclude_none=True),
                            status_code=ex.status_code)

    @app.exception_handler(RequestValidationError)
    async def on_request_error(request: Request, ex: RequestValidationError) -> JSONResponse:
        msg = utils.strex(ex)
        content = ErrorResponse(error=msg, validation=ex.errors())

        logger.error(f'[{request.url}] => {msg}')
        return JSONResponse(content.model_dump(mode='json', exclude_none=True),
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

    @app.exception_handler(ResponseValidationError)
    async def on_response_error(request: Request, ex: ResponseValidationError) -> JSONResponse:
        msg = utils.strex(ex)
        content = ErrorResponse(error=msg, validation=ex.errors())

        logger.error(f'[{request.url}] => {msg}')
        return JSONResponse(content.model_dump(mode='json', exclude_none=True),
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @app.exception_handler(Exception)
    async def on_generic_error(request: Request, ex: Exception) -> JSONResponse:  # pragma: no cover
        msg = utils.strex(ex)
        content = ErrorResponse(error=msg)

        if config.debug:
            content.traceback = traceback.format_exception(None, ex, ex.__traceback__)

        logger.error(f'[{request.url}] => {msg}', exc_info=config.debug)
        return JSONResponse(content.model_dump(exclude_none=True),
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@asynccontextmanager
async def lifespan(app: FastAPI):
    LOGGER.info(utils.get_config())
    LOGGER.trace('ROUTES:\n' + pformat(app.routes))
    LOGGER.trace('LOGGERS:\n' + pformat(logging.root.manager.loggerDict))

    async with AsyncExitStack() as stack:
        await stack.enter_async_context(mqtt.lifespan())
        await stack.enter_async_context(datastore_settings.lifespan())
        await stack.enter_async_context(connection.lifespan())
        await stack.enter_async_context(synchronization.lifespan())
        await stack.enter_async_context(broadcast.lifespan())
        await stack.enter_async_context(time_sync.lifespan())
        await stack.enter_async_context(block_backup.lifespan())
        yield


def create_app() -> FastAPI:
    config = utils.get_config()
    setup_logging(config.debug, config.trace)

    if config.debugger:  # pragma: no cover
        import debugpy
        debugpy.listen(('0.0.0.0', 5678))
        LOGGER.info('Debugger is enabled and listening on 5678')

    # Call setup functions for modules
    mqtt.setup()
    state_machine.setup()
    datastore_settings.setup()
    datastore_blocks.setup()
    codec.setup()
    connection.setup()
    command.setup()
    control.setup()
    block_backup.setup()
    blocks_mqtt_api.setup()

    # Create app
    # OpenApi endpoints are set to /api/doc for backwards compatibility
    prefix = f'/{config.name}'
    app = FastAPI(lifespan=lifespan,
                  docs_url=f'{prefix}/api/doc',
                  redoc_url=f'{prefix}/api/redoc',
                  openapi_url=f'{prefix}/openapi.json')

    # Set standardized error response
    add_exception_handlers(app)

    # Include all endpoints declared by modules
    app.include_router(blocks_api.router, prefix=prefix)
    app.include_router(system_api.router, prefix=prefix)
    app.include_router(settings_api.router, prefix=prefix)
    app.include_router(sim_api.router, prefix=prefix)
    app.include_router(backup_api.router, prefix=prefix)
    app.include_router(debug_api.router, prefix=prefix)

    return app
