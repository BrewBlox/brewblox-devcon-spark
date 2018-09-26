"""
Intermittently broadcasts controller state to the eventbus
"""


import asyncio
from concurrent.futures import CancelledError

from aiohttp import web
from brewblox_service import brewblox_logger, events, features, scheduler

from brewblox_devcon_spark import status
from brewblox_devcon_spark.api.object_api import (API_DATA_KEY, API_ID_KEY,
                                                  ObjectApi)

LOGGER = brewblox_logger(__name__)


def get_broadcaster(app: web.Application):
    return features.get(app, Broadcaster)


def setup(app: web.Application):
    features.add(app, Broadcaster(app))


class Broadcaster(features.ServiceFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)
        self._task: asyncio.Task = None

    def __str__(self):
        return f'{type(self).__name__}'

    @property
    def active(self):
        return bool(self._task and not self._task.done())

    async def startup(self, app: web.Application):
        await self.shutdown(app)
        self._task = await scheduler.create_task(app, self._broadcast())

    async def shutdown(self, _):
        await scheduler.cancel_task(self.app, self._task)
        self._task = None

    async def _broadcast(self):
        LOGGER.info(f'Starting {self}')

        try:
            api = ObjectApi(self.app)
            spark_status = status.get_status(self.app)
            publisher = events.get_publisher(self.app)
            name = self.app['config']['name']
            interval = self.app['config']['broadcast_interval']
            exchange = self.app['config']['broadcast_exchange']
            last_broadcast_ok = True

            if interval <= 0:
                LOGGER.info(f'Exiting {self} (disabled by user)')
                return

        except Exception as ex:
            LOGGER.error(f'{type(ex).__name__}: {str(ex)}', exc_info=True)
            raise ex

        while True:
            try:
                await spark_status.connected.wait()
                await asyncio.sleep(interval)
                current_objects = {
                    obj[API_ID_KEY]: obj[API_DATA_KEY]
                    for obj in await api.all()
                }

                # Don't broadcast when empty
                if not current_objects:
                    continue

                await publisher.publish(
                    exchange=exchange,
                    routing=name,
                    message=current_objects
                )

                if not last_broadcast_ok:
                    LOGGER.info(f'{self} resumed Ok')
                    last_broadcast_ok = True

            except CancelledError:
                break

            except Exception as ex:
                if last_broadcast_ok:
                    LOGGER.warn(f'{self} encountered an error: {type(ex).__name__}({ex})')
                    last_broadcast_ok = False
