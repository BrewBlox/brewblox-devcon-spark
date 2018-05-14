"""
Intermittently broadcasts controller state to the eventbus
"""


import asyncio
from concurrent.futures import CancelledError

from aiohttp import web
from brewblox_devcon_spark.api import ObjectApi
from brewblox_service import brewblox_logger, events, features

LOGGER = brewblox_logger(__name__)

BREWBLOX_EXCHANGE = 'brewblox'


def get_broadcaster(app: web.Application):
    return features.get(app, Broadcaster)


def setup(app: web.Application):
    features.add(app, Broadcaster(app))


class Broadcaster(features.ServiceFeature):

    def __init__(self, app: web.Application=None):
        super().__init__(app)
        self._task = None

    def __str__(self):
        return f'{type(self).__name__}'

    async def start(self, app: web.Application):
        await self.close()
        self._task = app.loop.create_task(self._broadcast(app))

    async def close(self, *args, **kwargs):
        try:
            self._task.cancel()
            await self._task
        except (AttributeError, CancelledError):
            pass
        finally:
            self._task = None

    async def _broadcast(self, app: web.Application):
        api = ObjectApi(app)
        publisher = events.get_publisher(app)
        name = app['config']['name']
        interval = app['config']['broadcast_interval']
        last_broadcast_ok = True

        LOGGER.info(f'{self} now broadcasting')

        while True:
            try:
                await asyncio.sleep(interval)
                state = await api.all_data()

                # Don't broadcast when empty
                if not state:
                    continue

                await publisher.publish(
                    exchange=BREWBLOX_EXCHANGE,
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
                    LOGGER.warn(f'{self} interrupted with error: {type(ex).__name__}={ex}')
                    last_broadcast_ok = False
