"""
Tests brewblox_devcon_spark.broadcaster
"""

import pytest
from asynctest import CoroutineMock
from brewblox_service import repeater, scheduler

from brewblox_devcon_spark import broadcaster, exceptions, state
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
    state.setup(app)
    scheduler.setup(app)
    return app


@pytest.fixture
async def connected(app, client):
    await state.on_synchronize(app)


async def test_noop_broadcast(app, mock_api, mock_publisher, client, connected):
    """The mock by default emits an empty list. This should not be published."""
    b = broadcaster.Broadcaster(app)
    await b.prepare()
    await b.run()
    assert mock_api.all_logged.call_count == 1
    assert mock_publisher.publish.call_count == 0


async def test_disabled(app, mock_api, mock_publisher, client, connected):
    app['config']['broadcast_interval'] = 0
    b = broadcaster.Broadcaster(app)
    with pytest.raises(repeater.RepeaterCancelled):
        await b.prepare()


async def test_broadcast(app, mock_api, mock_publisher, client, connected):
    object_list = [
        {API_SID_KEY: 'testey', API_DATA_KEY: {'var': 1}},
        {API_SID_KEY: 'testface', API_DATA_KEY: {'val': 2}}
    ]
    objects = {'testey': {'var': 1}, 'testface': {'val': 2}}
    mock_api.all_logged.return_value = object_list

    b = broadcaster.Broadcaster(app)
    await b.prepare()
    await b.run()

    mock_publisher.publish.assert_called_with(
        exchange='testcast', routing='test_app', message=objects)


async def test_error(app, mock_api, mock_publisher, client, connected):
    b = broadcaster.Broadcaster(app)
    await b.prepare()

    mock_api.all_logged.side_effect = RuntimeError
    with pytest.raises(RuntimeError):
        await b.run()

    mock_api.all_logged.side_effect = exceptions.ConnectionPaused
    await b.run()  # no throw

    # Error over, resume normal work
    mock_api.all_logged.side_effect = None
    mock_api.all_logged.return_value = [
        {API_SID_KEY: 'testey', API_DATA_KEY: {'var': 1}},
        {API_SID_KEY: 'testface', API_DATA_KEY: {'val': 2}}
    ]

    await b.run()
    assert mock_publisher.publish.call_count == 1
