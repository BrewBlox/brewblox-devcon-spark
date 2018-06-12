"""
Intermittently broadcasts controller state to the eventbus
"""


import asyncio
from concurrent.futures import CancelledError

from aiohttp import web
from brewblox_devcon_spark.api.object_api import ObjectApi
from brewblox_service import brewblox_logger, events, features

LOGGER = brewblox_logger(__name__)


def get_broadcaster(app: web.Application):
    return features.get(app, Broadcaster)


def setup(app: web.Application):
    features.add(app, Broadcaster(app))


class Broadcaster(features.ServiceFeature):

    def __init__(self, app: web.Application=None):
        super().__init__(app)
        self._task: asyncio.Task = None

    def __str__(self):
        return f'{type(self).__name__}'

    async def startup(self, app: web.Application):
        await self.shutdown()
        self._task = app.loop.create_task(self._broadcast(app))

    async def shutdown(self, *_):
        if self._task:
            self._task.cancel()
            await asyncio.wait([self._task])
        self._task = None

    async def _broadcast(self, app: web.Application):
        LOGGER.info(f'Starting {self}')

        try:
            api = ObjectApi(app)
            publisher = events.get_publisher(app)
            name = app['config']['name']
            interval = app['config']['broadcast_interval']
            exchange = app['config']['broadcast_exchange']
            last_broadcast_ok = True

        except Exception as ex:
            LOGGER.error(f'{type(ex).__name__}: {str(ex)}', exc_info=True)
            raise ex

        while True:
            try:
                await asyncio.sleep(interval)
                state = await api.all_data()

                # Don't broadcast when empty
                if not state:
                    continue

                await publisher.publish(
                    exchange=exchange,
                    routing=name,
                    message=state
                )

                if not last_broadcast_ok:
                    LOGGER.info(f'{self} resumed Ok')
                    last_broadcast_ok = True

            except CancelledError:
                break

            except Exception as ex:
                if last_broadcast_ok:
                    LOGGER.warn(f'{self} encountered an error: {type(ex).__name__}={ex}')
                    last_broadcast_ok = False
