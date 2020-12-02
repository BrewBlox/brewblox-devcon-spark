"""
Simulator-specific endpoints
"""

import asyncio
from weakref import WeakSet

from aiohttp import ClientSession, WSCloseCode, web
from aiohttp.http_websocket import WSMsgType
from brewblox_service import brewblox_logger, features

from brewblox_devcon_spark import service_status

SPARK_WS_ADDR = 'ws://localhost:7376/'

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()


class SocketCloser(features.ServiceFeature):

    def __init__(self, app: web.Application) -> None:
        super().__init__(app)
        app['websockets'] = WeakSet()

    async def startup(self, app: web.Application):
        pass

    async def before_shutdown(self, app: web.Application):
        for ws in set(app['websockets']):
            await ws.close(code=WSCloseCode.GOING_AWAY,
                           message='Server shutdown')

    async def shutdown(self, app: web.Application):
        pass


@routes.get('/sim/display')
async def stream_display(request: web.Request) -> web.Response:
    ws = web.WebSocketResponse()
    listen_task: asyncio.Task = None

    async def listen():
        async for msg in ws:  # pragma: no cover
            pass

    try:
        await ws.prepare(request)
        request.app['websockets'].add(ws)
        listen_task = asyncio.create_task(listen())

        await service_status.wait_synchronized(request.app)

        async with ClientSession() as session:
            # `Connection: keep-alive` is required by server
            async with session.ws_connect(
                SPARK_WS_ADDR,
                headers={'Connection': 'keep-alive, Upgrade'},
            ) as spark_ws:
                request.app['websockets'].add(spark_ws)
                async for msg in spark_ws:
                    if msg.type == WSMsgType.BINARY:
                        await ws.send_bytes(msg.data)
                request.app['websockets'].discard(spark_ws)

    finally:
        request.app['websockets'].discard(ws)
        listen_task and listen_task.cancel()

    return ws


def setup(app: web.Application):
    app.router.add_routes(routes)
    features.add(app, SocketCloser(app))
