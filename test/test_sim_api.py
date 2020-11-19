"""
Tests brewblox_devcon_spark.api.sim_api
"""

import asyncio

import pytest
from aiohttp import web
from aiohttp.client_ws import ClientWebSocketResponse
from aiohttp.http_websocket import WSMessage
from brewblox_service import scheduler
from mock import AsyncMock

from brewblox_devcon_spark.api import sim_api

TESTED = sim_api.__name__

routes = web.RouteTableDef()


@routes.get('/test_sim_api/stream')
async def stream_handler(request: web.Request) -> web.Response:
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    while True:
        print('sending...')
        await ws.send_str('ignored')
        await ws.send_bytes(bytes([1, 2, 3, 4]))
        await asyncio.sleep(0.1)
    return ws


@pytest.fixture
async def app(app):
    """App + controller routes"""
    scheduler.setup(app)
    sim_api.setup(app)
    app.router.add_routes(routes)

    return app


@pytest.fixture(autouse=True)
async def m_wait_sync(mocker):
    mocker.patch(TESTED + '.service_status.wait_synchronized', AsyncMock())


async def test_sim_display(app, client, mocker):
    mocker.patch(TESTED + '.SPARK_WS_ADDR', f'http://localhost:{client.port}/test_sim_api/stream')

    async with client.ws_connect('/sim/display') as ws:
        ws: ClientWebSocketResponse
        await ws.send_str('ignored')
        msg: WSMessage = await ws.receive_bytes(timeout=1)
        assert msg == bytes([1, 2, 3, 4])
