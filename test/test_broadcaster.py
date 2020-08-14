"""
Tests brewblox_devcon_spark.broadcaster
"""

import pytest
from brewblox_service import repeater, scheduler
from mock import ANY, AsyncMock, call

from brewblox_devcon_spark import broadcaster, exceptions, service_status

TESTED = broadcaster.__name__


@pytest.fixture
def m_api(mocker):
    m = mocker.patch(TESTED + '.BlocksApi', autospec=True)
    m.return_value.read_all = AsyncMock(return_value=[])
    m.return_value.read_all_logged = AsyncMock(return_value=[])
    return m.return_value


@pytest.fixture
def m_publish(mocker):
    mocker.patch(TESTED + '.mqtt.handler')
    m = mocker.patch(TESTED + '.mqtt.publish', AsyncMock())
    return m


@pytest.fixture
def app(app, m_api, m_publish):
    app['config']['broadcast_interval'] = 0.01
    app['config']['history_topic'] = 'testcast/history'
    app['config']['state_topic'] = 'testcast/state'
    app['config']['volatile'] = False
    service_status.setup(app)
    scheduler.setup(app)
    return app


@pytest.fixture
async def connected(app, client):
    service_status.set_synchronized(app)


async def test_noop_broadcast(app, m_api, m_publish, client, connected):
    """The mock by default emits an empty list. This should not be published to history"""
    b = broadcaster.Broadcaster(app)
    await b.prepare()
    await b.run()
    assert m_api.read_all_logged.call_count == 1
    assert m_api.read_all.call_count == 1
    assert m_publish.call_count == 3


async def test_disabled(app, m_api, m_publish, client, connected):
    app['config']['broadcast_interval'] = 0
    b = broadcaster.Broadcaster(app)
    with pytest.raises(repeater.RepeaterCancelled):
        await b.prepare()


async def test_broadcast_unsync(app, m_api, m_publish, client, connected, mocker):
    m_wait_sync = mocker.patch(TESTED + '.service_status.wait_synchronized', AsyncMock())
    m_wait_sync.return_value = False

    b = broadcaster.Broadcaster(app)
    await b.prepare()
    await b.run()

    assert m_wait_sync.call_count == 1
    assert m_publish.call_count == 3


async def test_broadcast(app, m_api, m_publish, client, connected):
    object_list = [
        {'id': 'testey', 'data': {'var': 1}},
        {'id': 'testface', 'data': {'val': 2}}
    ]
    objects = {'testey': {'var': 1}, 'testface': {'val': 2}}
    m_api.read_all_logged.return_value = object_list
    m_api.read_all.return_value = object_list

    b = broadcaster.Broadcaster(app)
    await b.prepare()
    await b.run()

    m_publish.assert_has_calls([
        call(app,
             'testcast/state/test_app',
             err=False,
             retain=True,
             message={
                 'key': 'test_app',
                 'type': 'Spark.state',
                 'ttl': '60.0s',
                 'data': {
                     'status': ANY,
                     'blocks': object_list,
                 },
             }),
        call(app,
             'testcast/history/test_app',
             err=False,
             message={
                 'key': 'test_app',
                 'data': objects,
             }),
        call(app,
             'testcast/state/test_app/blocks',
             err=False,
             retain=True,
             message={
                 'key': 'test_app',
                 'type': 'Spark.blocks',
                 'ttl': '60.0s',
                 'data': object_list,
             }),
    ])

    await b.before_shutdown(app)
    assert m_publish.call_count == 4


async def test_error(app, m_api, m_publish, client, connected):
    b = broadcaster.Broadcaster(app)
    await b.prepare()

    m_api.read_all.side_effect = RuntimeError
    with pytest.raises(RuntimeError):
        await b.run()

    m_api.read_all.side_effect = exceptions.ConnectionPaused
    await b.run()  # no throw

    # Error over, resume normal work
    m_api.read_all.side_effect = None
    m_api.read_all.return_value = [
        {'id': 'testey', 'data': {'var': 1}},
        {'id': 'testface', 'data': {'val': 2}}
    ]

    await b.run()
    assert m_publish.call_count == 3 * 3
