"""
Tests brewblox_devcon_spark.broadcaster
"""

import asyncio
from unittest.mock import call

import pytest
from asynctest import CoroutineMock
from brewblox_service import scheduler

from brewblox_devcon_spark import broadcaster
from brewblox_devcon_spark.device import OBJECT_DATA_KEY, OBJECT_ID_KEY

TESTED = broadcaster.__name__


@pytest.fixture
def mock_api(mocker):
    m = mocker.patch(TESTED + '.ObjectApi', autospec=True)
    m.return_value.list_active = CoroutineMock(return_value=[])
    return m.return_value


@pytest.fixture
def mock_publisher(mocker):
    m = mocker.patch(TESTED + '.events.get_publisher')
    m.return_value.publish = CoroutineMock()
    return m.return_value


@pytest.fixture
async def app(app, mock_api, mock_publisher):
    app['config']['broadcast_interval'] = 0.01
    app['config']['broadcast_exchange'] = 'testcast'
    scheduler.setup(app)
    broadcaster.setup(app)
    return app


@pytest.fixture
async def disabled_app(app):
    app['config']['broadcast_interval'] = 0
    return app


async def test_startup_shutdown(app, client):
    assert broadcaster.get_broadcaster(app)
    b = broadcaster.Broadcaster(app)
    await b.startup(app)
    await b.startup(app)
    await b.shutdown(app)
    await b.startup(app)
    await b.shutdown(app)


async def test_noop_broadcast(app, mock_api, mock_publisher, client):
    """The mock by default emits an empty list. This should not be published."""
    b = broadcaster.get_broadcaster(app)
    await asyncio.sleep(0.1)
    assert b.active
    assert mock_api.list_active.call_count > 0
    assert mock_publisher.publish.call_count == 0


async def test_disabled(disabled_app, mock_api, mock_publisher, client):
    b = broadcaster.get_broadcaster(disabled_app)
    await asyncio.sleep(0.1)
    assert not b.active
    assert mock_api.list_active.call_count == 0
    assert mock_publisher.publish.call_count == 0


async def test_broadcast(mock_api, mock_publisher, client):
    object_list = [
        {OBJECT_ID_KEY: 'testey', OBJECT_DATA_KEY: {'var': 1}},
        {OBJECT_ID_KEY: 'testface', OBJECT_DATA_KEY: {'val': 2}}
    ]
    objects = {'testey': {'var': 1}, 'testface': {'val': 2}}
    mock_api.list_active.return_value = object_list
    await asyncio.sleep(0.1)

    assert call(exchange='testcast', routing='test_app', message=objects) in mock_publisher.publish.mock_calls


async def test_error(app, client, mock_api, mock_publisher):
    b = broadcaster.get_broadcaster(app)

    # Don't exit after error
    mock_api.list_active.side_effect = RuntimeError

    await asyncio.sleep(0.1)
    assert not b._task.done()
    assert mock_publisher.publish.call_count == 0

    # Error over, resume normal work
    mock_api.list_active.side_effect = None
    mock_api.list_active.return_value = [
        {OBJECT_ID_KEY: 'testey', OBJECT_DATA_KEY: {'var': 1}},
        {OBJECT_ID_KEY: 'testface', OBJECT_DATA_KEY: {'val': 2}}
    ]

    await asyncio.sleep(0.1)
    assert not b._task.done()
    assert mock_publisher.publish.call_count > 0


async def test_startup_error(app, client, mocker):
    logger_spy = mocker.spy(broadcaster, 'LOGGER')

    del app['config']['broadcast_interval']

    b = broadcaster.Broadcaster(app)

    await b.startup(app)
    await asyncio.sleep(0.01)
    assert logger_spy.error.call_count == 1
    await b.shutdown(app)
