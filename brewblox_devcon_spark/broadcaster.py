"""
Intermittently broadcasts controller state to the eventbus
"""


import asyncio
from concurrent.futures import CancelledError

from aiohttp import web
from brewblox_service import (brewblox_logger, events, features, scheduler,
                              strex)

from brewblox_devcon_spark import exceptions, status
from brewblox_devcon_spark.api.object_api import (API_DATA_KEY, API_SID_KEY,
                                                  ObjectApi)
from brewblox_devcon_spark.device import GENERATED_ID_PREFIX

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
        try:
            name = self.app['config']['name']
            interval = self.app['config']['broadcast_interval']
            exchange = self.app['config']['broadcast_exchange']

            if interval <= 0 or self.app['config']['volatile']:
                LOGGER.info(f'{self} disabled by user')
                return

            LOGGER.info(f'Starting {self}')

            api = ObjectApi(self.app)
            spark_status = status.get_status(self.app)
            publisher = events.get_publisher(self.app)
            last_broadcast_ok = True

        except Exception as ex:
            LOGGER.error(f'{type(ex).__name__}: {str(ex)}', exc_info=True)
            raise ex

        while True:
            try:
                await spark_status.wait_synchronize()
                await asyncio.sleep(interval)
                current_objects = {
                    obj[API_SID_KEY]: obj[API_DATA_KEY]
                    for obj in await api.all_logged()
                    if not obj[API_SID_KEY].startswith(GENERATED_ID_PREFIX)
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

            except exceptions.ConnectionPaused:
                LOGGER.debug(f'{self} interrupted: connection paused')
                last_broadcast_ok = False

            except Exception as ex:
                if last_broadcast_ok:
                    LOGGER.error(f'{self} encountered an error: {strex(ex)}')
                    last_broadcast_ok = False
