"""
SSE API for subscribing to periodic updates
"""

import asyncio
import json
import weakref
from typing import Set

from aiohttp import hdrs, web
from aiohttp_sse import sse_response
from brewblox_service import brewblox_logger, features, repeater, strex

from brewblox_devcon_spark import exceptions, state
from brewblox_devcon_spark.api.object_api import ObjectApi

PUBLISH_INTERVAL_S = 5

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()


def get_publisher(app: web.Application):
    return features.get(app, SSEPublisher)


def setup(app: web.Application):
    app.router.add_routes(routes)
    features.add(app, SSEPublisher(app))


class SSEPublisher(repeater.RepeaterFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)
        self._queues: Set[asyncio.Queue] = weakref.WeakSet()
        self._current = None

    async def subscribe(self, queue: asyncio.Queue):
        self._queues.add(queue)
        try:
            if self._current is None:
                self._current = await ObjectApi(self.app).all()
            await queue.put(self._current)

        except asyncio.CancelledError:  # pragma: no cover
            raise

        except Exception as ex:
            LOGGER.info(f'Initial subscription push failed: {strex(ex)}')

    async def before_shutdown(self, _):
        for queue in self._queues:
            await queue.put(asyncio.CancelledError())

    async def prepare(self):
        LOGGER.info(f'Starting {self}')

    async def run(self):
        api = ObjectApi(self.app)

        try:
            await state.wait_synchronize(self.app)
            await asyncio.sleep(PUBLISH_INTERVAL_S)

            if not self._queues:
                self._current = None
                return

            self._current = await api.all()
            coros = [q.put(self._current) for q in self._queues]
            await asyncio.wait_for(asyncio.gather(*coros, return_exceptions=True), PUBLISH_INTERVAL_S)

        except exceptions.ConnectionPaused:
            self._current = None


def _cors_headers(request):
    return {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods':
        request.headers.get('Access-Control-Request-Method', ','.join(hdrs.METH_ALL)),
        'Access-Control-Allow-Headers':
        request.headers.get('Access-Control-Request-Headers', '*'),
        'Access-Control-Allow-Credentials': 'true',
    }


@routes.get('/sse/objects')
async def subscribe(request: web.Request) -> web.Response:
    """
    ---
    summary: Periodically pushes all active objects
    tags:
    - Spark
    - Objects
    operationId: controller.spark.sse.objects
    produces:
    - application/json
    """
    async with sse_response(request, headers=_cors_headers(request)) as resp:
        publisher: SSEPublisher = get_publisher(request.app)
        queue = asyncio.Queue()
        await publisher.subscribe(queue)

        while True:
            data = await queue.get()
            if isinstance(data, Exception):
                raise data
            await resp.send(json.dumps(data))

    # Note: we don't ever expect to return the response
    # Either the client cancels the request, or an exception is raised by publisher
