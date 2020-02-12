"""
Tests brewblox_devcon_spark.broadcaster
"""

from unittest.mock import ANY, AsyncMock, call

import pytest
from brewblox_service import repeater, scheduler

from brewblox_devcon_spark import broadcaster, exceptions, state
from brewblox_devcon_spark.api.object_api import API_DATA_KEY, API_SID_KEY

TESTED = broadcaster.__name__


@pytest.fixture
def mock_api(mocker):
    m = mocker.patch(TESTED + '.ObjectApi', autospec=True)
    m.return_value.all = AsyncMock(return_value=[])
    m.return_value.all_logged = AsyncMock(return_value=[])
    return m.return_value


@pytest.fixture
def mock_publisher(mocker):
    m = mocker.patch(TESTED + '.events.get_publisher')
    m.return_value.publish = AsyncMock()
    return m.return_value


@pytest.fixture
async def app(app, mock_api, mock_publisher):
    app['config']['broadcast_interval'] = 0.01
    app['config']['history_exchange'] = 'testcast.history'
    app['config']['state_exchange'] = 'testcast.state'
    app['config']['volatile'] = False
    state.setup(app)
    scheduler.setup(app)
    return app


@pytest.fixture
async def connected(app, client):
    await state.on_synchronize(app)


async def test_noop_broadcast(app, mock_api, mock_publisher, client, connected):
    """The mock by default emits an empty list. This should not be published to history"""
    b = broadcaster.Broadcaster(app)
    await b.prepare()
    await b.run()
    assert mock_api.all_logged.call_count == 1
    assert mock_api.all.call_count == 1
    assert mock_publisher.publish.call_count == 2


async def test_disabled(app, mock_api, mock_publisher, client, connected):
    app['config']['broadcast_interval'] = 0
    b = broadcaster.Broadcaster(app)
    with pytest.raises(repeater.RepeaterCancelled):
        await b.prepare()


async def test_broadcast_unsync(app, mock_api, mock_publisher, client, connected, mocker):
    m_wait_sync = mocker.patch(TESTED + '.state.wait_synchronize', AsyncMock())
    m_wait_sync.return_value = False

    b = broadcaster.Broadcaster(app)
    await b.prepare()
    await b.run()

    assert m_wait_sync.call_count == 1
    assert mock_publisher.publish.call_count == 1


async def test_broadcast(app, mock_api, mock_publisher, client, connected):
    object_list = [
        {API_SID_KEY: 'testey', API_DATA_KEY: {'var': 1}},
        {API_SID_KEY: 'testface', API_DATA_KEY: {'val': 2}}
    ]
    objects = {'testey': {'var': 1}, 'testface': {'val': 2}}
    mock_api.all_logged.return_value = object_list
    mock_api.all.return_value = object_list

    b = broadcaster.Broadcaster(app)
    await b.prepare()
    await b.run()

    mock_publisher.publish.assert_has_calls([
        call(exchange='testcast.state',
             routing='test_app',
             message={
                 'key': 'test_app',
                 'type': 'Spark.service',
                 'duration': '30s',
                 'data': ANY,
             }),
        call(exchange='testcast.state',
             routing='test_app',
             message={
                 'key': 'test_app',
                 'type': 'Spark.blocks',
                 'duration': '30s',
                 'data': object_list,
             }),
        call(exchange='testcast.history',
             routing='test_app',
             message=objects,
             )
    ])


async def test_error(app, mock_api, mock_publisher, client, connected):
    b = broadcaster.Broadcaster(app)
    await b.prepare()

    mock_api.all.side_effect = RuntimeError
    with pytest.raises(RuntimeError):
        await b.run()

    mock_api.all.side_effect = exceptions.ConnectionPaused
    await b.run()  # no throw

    # Error over, resume normal work
    mock_api.all.side_effect = None
    mock_api.all.return_value = [
        {API_SID_KEY: 'testey', API_DATA_KEY: {'var': 1}},
        {API_SID_KEY: 'testface', API_DATA_KEY: {'val': 2}}
    ]

    await b.run()
    assert mock_publisher.publish.call_count == 3 + 1
