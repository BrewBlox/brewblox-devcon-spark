"""
Maintains the object cache
"""
import asyncio
from concurrent.futures import CancelledError

from aiohttp import web
from brewblox_devcon_spark.api.object_api import ObjectApi
from brewblox_service import brewblox_logger, features

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()


def setup(app: web.Application):
    features.add(app, CacheUpdater(app))


class CacheUpdater(features.ServiceFeature):
    def __init__(self, app: web.Application=None):
        super().__init__(app)
        self._task: asyncio.Task = None

    def __str__(self):
        return f'{type(self).__name__}'

    async def startup(self, app: web.Application):
        await self.shutdown()
        self._task = app.loop.create_task(self._update(app))

    async def shutdown(self, *_):
        if self._task:
            self._task.cancel()
            await asyncio.wait([self._task])
            self._task = None

    async def _update(self, app: web.Application):
        LOGGER.info(f'Starting {self}')

        try:
            api = ObjectApi(app)
            interval = app['config']['update_interval']

        except Exception as ex:
            LOGGER.error(f'{type(ex).__name__}: {str(ex)}', exc_info=True)
            raise ex

        while True:
            try:
                await asyncio.sleep(interval)
                await api.all(refresh=True)

            except CancelledError:
                break

            except Exception as ex:  # pragma: no cover
                LOGGER.warn(f'{self} encountered an error: {type(ex).__name__}={ex}')
