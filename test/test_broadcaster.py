"""
Tests brewblox_devcon_spark.broadcaster
"""

import asyncio
from unittest.mock import call

import pytest
from asynctest import CoroutineMock
from brewblox_service import scheduler

from brewblox_devcon_spark import broadcaster, exceptions, status
from brewblox_devcon_spark.api.object_api import API_DATA_KEY, API_SID_KEY

TESTED = broadcaster.__name__


@pytest.fixture
def mock_api(mocker):
    m = mocker.patch(TESTED + '.ObjectApi', autospec=True)
    m.return_value.all_logged = CoroutineMock(return_value=[])
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
    app['config']['volatile'] = False
    status.setup(app)
    scheduler.setup(app)
    broadcaster.setup(app)
    return app


@pytest.fixture
async def disabled_app(app):
    app['config']['broadcast_interval'] = 0
    return app


@pytest.fixture
async def connected(app, client):
    await status.get_status(app).on_synchronize()


async def test_startup_shutdown(app, client):
    assert broadcaster.get_broadcaster(app)
    b = broadcaster.Broadcaster(app)
    await b.startup(app)
    await b.startup(app)
    await b.shutdown(app)
    await b.startup(app)
    await b.shutdown(app)


async def test_noop_broadcast(app, mock_api, mock_publisher, client, connected):
    """The mock by default emits an empty list. This should not be published."""
    b = broadcaster.get_broadcaster(app)
    await asyncio.sleep(0.1)
    assert b.active
    assert mock_api.all_logged.call_count > 0
    assert mock_publisher.publish.call_count == 0


async def test_disabled(disabled_app, mock_api, mock_publisher, client, connected):
    b = broadcaster.get_broadcaster(disabled_app)
    await asyncio.sleep(0.1)
    assert not b.active
    assert mock_api.all_logged.call_count == 0
    assert mock_publisher.publish.call_count == 0


async def test_broadcast(mock_api, mock_publisher, client, connected):
    object_list = [
        {API_SID_KEY: 'testey', API_DATA_KEY: {'var': 1}},
        {API_SID_KEY: 'testface', API_DATA_KEY: {'val': 2}}
    ]
    objects = {'testey': {'var': 1}, 'testface': {'val': 2}}
    mock_api.all_logged.return_value = object_list
    await asyncio.sleep(0.1)

    assert call(exchange='testcast', routing='test_app', message=objects) in mock_publisher.publish.mock_calls


@pytest.mark.parametrize('err', [
    RuntimeError,
    exceptions.ConnectionPaused,
])
async def test_error(err, app, client, mock_api, mock_publisher, connected):
    b = broadcaster.get_broadcaster(app)

    # Don't exit after error
    mock_api.all_logged.side_effect = err

    await asyncio.sleep(0.1)
    assert not b._task.done()
    assert mock_publisher.publish.call_count == 0

    # Error over, resume normal work
    mock_api.all_logged.side_effect = None
    mock_api.all_logged.return_value = [
        {API_SID_KEY: 'testey', API_DATA_KEY: {'var': 1}},
        {API_SID_KEY: 'testface', API_DATA_KEY: {'val': 2}}
    ]

    await asyncio.sleep(0.1)
    assert not b._task.done()
    assert mock_publisher.publish.call_count > 0


async def test_startup_error(app, client, mocker, connected):
    logger_spy = mocker.spy(broadcaster, 'LOGGER')

    del app['config']['broadcast_interval']

    b = broadcaster.Broadcaster(app)

    await b.startup(app)
    await asyncio.sleep(0.01)
    assert logger_spy.error.call_count == 1
    await b.shutdown(app)
