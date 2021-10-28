"""
Tests brewblox_devcon_spark.broadcaster
"""

from copy import deepcopy
from unittest.mock import ANY, AsyncMock, call

import pytest
from brewblox_service import repeater, scheduler

from brewblox_devcon_spark import (block_cache, block_store, broadcaster,
                                   commander_sim, exceptions, global_store,
                                   service_status, service_store, spark,
                                   synchronization)
from brewblox_devcon_spark.codec import codec, unit_conversion

TESTED = broadcaster.__name__


@pytest.fixture(autouse=True)
def m_relations(mocker):
    mocker.patch(TESTED + '.calculate_relations', autospec=True)
    mocker.patch(TESTED + '.calculate_drive_chains', autospec=True)


@pytest.fixture
def m_api(mocker):
    m = mocker.patch(TESTED + '.BlocksApi', autospec=True)
    m.return_value.read_all_broadcast = AsyncMock(return_value=([], []))
    return m.return_value


@pytest.fixture
def m_publish(mocker):
    mocker.patch(TESTED + '.mqtt.handler', autospec=True)
    m = mocker.patch(TESTED + '.mqtt.publish', autospec=True)
    return m


@pytest.fixture
def app(app):
    app['config']['broadcast_interval'] = 0.01
    app['config']['history_topic'] = 'testcast/history'
    app['config']['state_topic'] = 'testcast/state'
    service_status.setup(app)
    scheduler.setup(app)
    block_cache.setup(app)
    return app


@pytest.fixture
def api_app(app):
    commander_sim.setup(app)
    block_store.setup(app)
    global_store.setup(app)
    service_store.setup(app)
    unit_conversion.setup(app)
    codec.setup(app)
    synchronization.setup(app)
    spark.setup(app)
    return app


@pytest.fixture
async def connected(app, client):
    service_status.set_synchronized(app)


async def test_noop_broadcast(app, m_api, m_publish, client, connected):
    """The mock by default emits an empty list. This should not be published to history"""
    app['config']['volatile'] = False
    b = broadcaster.Broadcaster(app)
    await b.prepare()
    await b.run()
    assert m_api.read_all_broadcast.call_count == 1
    assert m_publish.call_count == 2


async def test_disabled(app, m_api, m_publish, client, connected):
    app['config']['broadcast_interval'] = 0
    app['config']['volatile'] = False
    b = broadcaster.Broadcaster(app)
    with pytest.raises(repeater.RepeaterCancelled):
        await b.prepare()


async def test_broadcast_unsync(app, m_api, m_publish, client, connected, mocker):
    m_wait_sync = mocker.patch(TESTED + '.service_status.wait_synchronized', AsyncMock())
    m_wait_sync.return_value = False

    app['config']['volatile'] = False
    b = broadcaster.Broadcaster(app)
    await b.prepare()
    await b.run()

    assert m_wait_sync.call_count == 1
    assert m_publish.call_count == 1


async def test_broadcast(app, m_api, m_publish, client, connected):
    object_list = [
        {'id': 'testey', 'nid': 1, 'data': {'var': 1}},
        {'id': 'testface', 'nid': 2, 'data': {'val': 2}}
    ]
    objects = {'testey': {'var': 1}, 'testface': {'val': 2}}
    m_api.read_all_broadcast.return_value = (
        deepcopy(object_list),
        deepcopy(object_list)
    )

    app['config']['volatile'] = False
    b = broadcaster.Broadcaster(app)
    await b.prepare()
    await b.run()

    m_publish.assert_has_calls([
        call(app,
             'testcast/history/test_app',
             err=False,
             message={
                 'key': 'test_app',
                 'data': objects,
             }),
        call(app,
             'testcast/state/test_app',
             err=False,
             retain=True,
             message={
                 'key': 'test_app',
                 'type': 'Spark.state',
                 'data': {
                     'status': ANY,
                     'blocks': object_list,
                     'relations': ANY,
                     'drive_chains': ANY,
                 },
             }),
    ])

    await b.before_shutdown(app)
    assert m_publish.call_count == 3


async def test_error(app, m_api, m_publish, client, connected):
    app['config']['volatile'] = False
    b = broadcaster.Broadcaster(app)
    await b.prepare()

    m_api.read_all_broadcast.side_effect = RuntimeError
    with pytest.raises(RuntimeError):
        await b.run()

    m_api.read_all_broadcast.side_effect = exceptions.ConnectionPaused
    await b.run()  # no throw

    # Error over, resume normal work
    m_api.read_all_broadcast.side_effect = None
    m_api.read_all_broadcast.return_value = (
        [
            {'id': 'testey', 'nid': 1, 'data': {'var': 1}},
            {'id': 'testface', 'nid': 2, 'data': {'val': 2}}
        ],
        [
            {'id': 'testey', 'nid': 1, 'data': {'var': 1}},
            {'id': 'testface', 'nid': 2, 'data': {'val': 2}}
        ],
    )

    # 2 * only state event
    # 1 * history + state
    await b.run()
    assert m_publish.call_count == 4


async def test_api_broadcaster(app, api_app, m_publish, client):
    await service_status.wait_synchronized(app)
    app['config']['volatile'] = False
    b = broadcaster.Broadcaster(app)
    await b.prepare()
    await b.run()
    assert m_publish.call_count == 2
