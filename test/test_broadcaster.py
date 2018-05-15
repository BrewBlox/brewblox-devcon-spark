"""
Tests brewblox_devcon_spark.broadcaster
"""

import asyncio

from asynctest import CoroutineMock
from unittest.mock import call

import pytest
from brewblox_devcon_spark import broadcaster

TESTED = broadcaster.__name__


@pytest.fixture
def mock_api(mocker):
    m = mocker.patch(TESTED + '.ObjectApi')
    m.return_value.all_data = CoroutineMock(return_value=[])
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
    broadcaster.setup(app)
    return app


async def test_startup_close(app, client):
    assert broadcaster.get_broadcaster(app)
    b = broadcaster.Broadcaster()
    await b.start(app)
    await b.start(app)
    await b.close(app)
    await b.start(app)
    await b.close(app)


async def test_noop_broadcast(mock_api, mock_publisher, client):
    """The mock by default emits an empty list. This should not be published."""
    await asyncio.sleep(0.1)
    assert mock_api.all_data.call_count > 0
    assert mock_publisher.publish.call_count == 0


async def test_broadcast(mock_api, mock_publisher, client):
    objects = {'testey': {'var': 1}, 'testface': {'val': 2}}
    mock_api.all_data.return_value = objects
    await asyncio.sleep(0.1)

    assert call(exchange='testcast', routing='test_app', message=objects) in mock_publisher.publish.mock_calls


async def test_error(app, client, mock_api, mock_publisher):
    b = broadcaster.get_broadcaster(app)

    # Don't exit after error
    mock_api.all_data.side_effect = RuntimeError

    await asyncio.sleep(0.1)
    assert not b._task.done()
    assert mock_publisher.publish.call_count == 0

    # Error over, resume normal work
    mock_api.all_data.side_effect = None
    mock_api.all_data.return_value = {'brought': 'shrubbery'}

    await asyncio.sleep(0.1)
    assert not b._task.done()
    assert mock_publisher.publish.call_count > 0
