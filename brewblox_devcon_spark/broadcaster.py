"""
Intermittently broadcasts controller state to the eventbus
"""


import asyncio
from concurrent.futures import CancelledError

from aiohttp import web
from brewblox_service import events

from brewblox_devcon_spark import brewblox_logger
from brewblox_devcon_spark.api import ObjectApi

LOGGER = brewblox_logger(__name__)

BREWBLOX_EXCHANGE = 'brewblox'


def get_broadcaster(app: web.Application):
    return app[Broadcaster.__name__]


def setup(app: web.Application):
    app[Broadcaster.__name__] = Broadcaster(app)


class Broadcaster():

    def __init__(self, app: web.Application=None):
        self._task = None
        # TODO(Bob): use get_publisher(app) call after events.setup() is split
        # See https://github.com/BrewBlox/brewblox-service/issues/65
        self._publisher = events.EventPublisher(app)

        if app:
            self.setup(app)

    def __str__(self):
        return f'{type(self).__name__}'

    def setup(self, app: web.Application):
        app.on_startup.append(self.start)
        app.on_cleanup.append(self.close)

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

                await self._publisher.publish(
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
