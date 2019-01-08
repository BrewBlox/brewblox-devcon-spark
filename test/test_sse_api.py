"""
Tests brewblox_devcon_spark.api.sse_api
"""

import asyncio

import pytest
from aiohttp.client_exceptions import ClientPayloadError
from asynctest import CoroutineMock
from brewblox_service import scheduler

from brewblox_devcon_spark import (commander_sim, datastore, device, seeder,
                                   status)
from brewblox_devcon_spark.api import error_response, sse_api
from brewblox_devcon_spark.codec import codec

TESTED = sse_api.__name__


@pytest.fixture
async def app(app, loop, mocker):
    """App + controller routes"""
    mocker.patch(TESTED + '.PUBLISH_INTERVAL_S', 0.001)

    status.setup(app)
    scheduler.setup(app)
    commander_sim.setup(app)
    datastore.setup(app)
    seeder.setup(app)
    codec.setup(app)
    device.setup(app)

    error_response.setup(app)
    sse_api.setup(app)

    return app


@pytest.fixture
async def publisher(app):
    return sse_api.get_publisher(app)


async def test_immediate_result(app, client, mocker):
    api_mock = mocker.patch(TESTED + '.ObjectApi').return_value
    api_mock.all = CoroutineMock(side_effect=['one', 'two', 'three'])

    mocker.patch(TESTED + '.PUBLISH_INTERVAL_S', 1)

    pub = sse_api.SSEPublisher(app)
    await pub.startup(app)
    await asyncio.sleep(0.01)
    assert api_mock.all.call_count == 0

    q1, q2 = asyncio.Queue(), asyncio.Queue()
    await pub.subscribe(q1)
    await pub.subscribe(q2)
    await asyncio.sleep(0.01)
    assert api_mock.all.call_count == 1
    assert q1.get_nowait() == 'one'
    assert q2.get_nowait() == 'one'


async def test_error_setup(app, client, mocker):
    api_mock = mocker.patch(TESTED + '.ObjectApi')
    api_mock.side_effect = RuntimeError

    # Application should not crash because of startup errors
    pub = sse_api.SSEPublisher(app)
    await pub.startup(app)
    await asyncio.sleep(0.01)
    assert api_mock.call_count == 1


async def test_error_call(app, client, mocker):
    api_mock = mocker.patch(TESTED + '.ObjectApi').return_value
    api_mock.all = CoroutineMock(side_effect=RuntimeError)

    pub = sse_api.SSEPublisher(app)
    await pub.startup(app)

    # There are no requests - don't call API
    await asyncio.sleep(0.01)
    assert api_mock.all.call_count == 0

    # Do not crash if api.all() raises exceptions
    queue = asyncio.Queue()
    await pub.subscribe(queue)
    await asyncio.sleep(0.1)
    assert api_mock.all.call_count > 1
    assert queue.empty()


async def test_sse_objects(app, client, publisher):
    async with client.get('/sse/objects') as resp:
        chunk = await resp.content.read(5)
        assert chunk.decode() == 'data:'


async def test_close(app, client, publisher):
    with pytest.raises(ClientPayloadError):
        async with client.get('/sse/objects') as resp:
            await publisher.before_shutdown(app)
            await resp.content.read(5)
            await resp.content.read(5)
