"""
Tests brewblox_devcon_spark.api.sse_api
"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from aiohttp.client_exceptions import ClientPayloadError

from brewblox_devcon_spark import (commander_sim, datastore, device,
                                   exceptions, seeder, state)
from brewblox_devcon_spark.api import error_response, sse_api
from brewblox_devcon_spark.codec import codec
from brewblox_service import scheduler

TESTED = sse_api.__name__


@pytest.fixture
async def app(app, mocker):
    """App + controller routes"""
    mocker.patch(TESTED + '.PUBLISH_INTERVAL_S', 0.001)

    state.setup(app)
    scheduler.setup(app)
    commander_sim.setup(app)
    datastore.setup(app)
    seeder.setup(app)
    codec.setup(app)
    device.setup(app)

    error_response.setup(app)

    return app


@pytest.fixture
async def sse(app):
    sse_api.setup(app)


@pytest.fixture
async def api_mock(mocker):
    m = mocker.patch(TESTED + '.ObjectApi').return_value
    m.all = AsyncMock()
    return m


@pytest.fixture
async def publisher(app):
    return sse_api.get_publisher(app)


async def test_caching(app, api_mock, client, mocker):
    api_mock.all.side_effect = ['one', 'two', 'three']

    pub = sse_api.SSEPublisher(app)
    await pub.prepare()

    # No subscribers -> don't bother getting objects
    await pub.run()
    await pub.run()
    assert api_mock.all.call_count == 0

    # Current is empty -> immediately get objects
    q1, q2 = asyncio.Queue(), asyncio.Queue()
    await pub.subscribe(q1)
    await pub.subscribe(q2)
    assert q1.get_nowait() == 'one'
    assert q2.get_nowait() == 'one'

    # We have subscribers -> they both get an update
    await pub.run()
    assert q1.get_nowait() == 'two'
    assert q2.get_nowait() == 'two'


async def test_empty_call(app, client):
    pub = sse_api.SSEPublisher(app)
    await pub.prepare()
    await pub.run()


async def test_error_call(app, client, mocker):
    api_mock = mocker.patch(TESTED + '.ObjectApi').return_value
    api_mock.all = AsyncMock()

    pub = sse_api.SSEPublisher(app)
    queue = asyncio.Queue()
    await pub.prepare()

    api_mock.all.side_effect = RuntimeError
    await pub.subscribe(queue)  # no error
    assert api_mock.all.call_count == 1

    with pytest.raises(RuntimeError):
        await pub.run()
    assert api_mock.all.call_count == 2
    assert queue.empty()

    api_mock.all.side_effect = exceptions.ConnectionPaused
    await pub.run()
    assert api_mock.all.call_count == 3
    assert queue.empty()


async def test_sse_objects(app, sse, client, publisher):
    async with client.get('/sse/objects') as resp:
        chunk = await resp.content.read(5)
        assert chunk.decode() == 'data:'


async def test_close(app, sse, client, publisher):
    with pytest.raises(ClientPayloadError):
        async with client.get('/sse/objects') as resp:
            await publisher.before_shutdown(app)
            await resp.content.read(5)
            await resp.content.read(5)
