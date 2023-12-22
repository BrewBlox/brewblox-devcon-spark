import logging
from contextlib import AsyncExitStack, asynccontextmanager
from pprint import pformat

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from . import (backup_storage, broadcaster, codec, commander, connection,
               controller, datastore, mqtt, service_status, synchronization,
               time_sync, utils)
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

    @app.exception_handler(Exception)
    async def catchall_handler(request: Request, exc: Exception) -> JSONResponse:
        short = utils.strex(exc)
        details = utils.strex(exc, tb=config.debug)
        content = ErrorResponse(error=str(exc),
                                details=details)

        if isinstance(exc, HTTPException):
            status_code = exc.status_code
        else:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

        logger.error(f'[{request.url}] => {short}')
        logger.debug(details)
        return JSONResponse(content.model_dump(), status_code=status_code)


@asynccontextmanager
async def lifespan(app: FastAPI):
    LOGGER.info(utils.get_config())
    LOGGER.debug('ROUTES:\n' + pformat(app.routes))
    LOGGER.debug('LOGGERS:\n' + pformat(logging.root.manager.loggerDict))

    async with AsyncExitStack() as stack:
        await stack.enter_async_context(mqtt.lifespan())
        await stack.enter_async_context(datastore.lifespan())
        await stack.enter_async_context(connection.lifespan())
        await stack.enter_async_context(synchronization.lifespan())
        await stack.enter_async_context(backup_storage.lifespan())
        await stack.enter_async_context(broadcaster.lifespan())
        await stack.enter_async_context(time_sync.lifespan())
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
    service_status.setup()
    datastore.setup()
    codec.setup()
    connection.setup()
    commander.setup()
    controller.setup()
    backup_storage.setup()
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
