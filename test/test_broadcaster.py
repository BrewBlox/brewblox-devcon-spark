"""
Tests brewblox_devcon_spark.broadcaster
"""

from unittest.mock import ANY, AsyncMock, call

import pytest
from brewblox_service import repeater, scheduler

from brewblox_devcon_spark import (block_store, broadcaster, codec, commander,
                                   connection_sim, controller, exceptions,
                                   global_store, service_status, service_store,
                                   synchronization)
from brewblox_devcon_spark.models import ErrorCode

TESTED = broadcaster.__name__


@pytest.fixture(autouse=True)
def m_relations(mocker):
    mocker.patch(TESTED + '.calculate_relations', autospec=True)
    mocker.patch(TESTED + '.calculate_claims', autospec=True)


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
    codec.setup(app)
    block_store.setup(app)
    global_store.setup(app)
    service_store.setup(app)
    connection_sim.setup(app)
    commander.setup(app)
    synchronization.setup(app)
    controller.setup(app)
    return app


@pytest.fixture
async def synchronized(app, client):
    await service_status.wait_synchronized(app)


async def test_disabled(app, m_publish, client, synchronized):
    app['config']['broadcast_interval'] = 0
    app['config']['volatile'] = False
    b = broadcaster.Broadcaster(app)
    with pytest.raises(repeater.RepeaterCancelled):
        await b.prepare()


async def test_broadcast_unsync(app, m_publish, client, synchronized, mocker):
    m_wait_sync = mocker.patch(TESTED + '.service_status.wait_synchronized', AsyncMock())
    m_wait_sync.return_value = False

    app['config']['volatile'] = False
    b = broadcaster.Broadcaster(app)
    await b.prepare()
    await b.run()

    assert m_wait_sync.call_count == 1
    assert m_publish.call_count == 1


async def test_broadcast(app, m_publish, client, synchronized):
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
                 'data': ANY,
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
                     'blocks': ANY,
                     'relations': ANY,
                     'claims': ANY,
                 },
             }),
    ])

    await b.before_shutdown(app)
    assert m_publish.call_count == 3


async def test_error(app, m_publish, client, synchronized):
    app['config']['volatile'] = False
    b = broadcaster.Broadcaster(app)
    await b.prepare()

    connection_sim.fget(app).next_error.append(ErrorCode.UNKNOWN_ERROR)
    with pytest.raises(exceptions.CommandException):
        await b.run()

    # Error over, resume normal work
    # 1 * only state event
    # 1 * history + state
    await b.run()
    assert m_publish.call_count == 3


async def test_api_broadcaster(app, m_publish, client):
    await service_status.wait_synchronized(app)
    app['config']['volatile'] = False
    b = broadcaster.Broadcaster(app)
    await b.prepare()
    await b.run()
    assert m_publish.call_count == 2
