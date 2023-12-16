"""
Tests brewblox_devcon_spark.broadcaster
"""

from unittest.mock import ANY, Mock, call

import pytest
from brewblox_service import mqtt, repeater, scheduler
from pytest_mock import MockerFixture

from brewblox_devcon_spark import (block_store, broadcaster, codec, commander,
                                   connection, controller, exceptions,
                                   global_store, service_status, service_store,
                                   synchronization)
from brewblox_devcon_spark.connection import mock_connection
from brewblox_devcon_spark.models import ErrorCode, ServiceConfig

TESTED = broadcaster.__name__


@pytest.fixture(autouse=True)
def m_relations(mocker):
    mocker.patch(TESTED + '.calculate_relations',
                 autospec=True,
                 side_effect=lambda blocks: {})
    mocker.patch(TESTED + '.calculate_claims',
                 autospec=True,
                 side_effect=lambda blocks: {})


@pytest.fixture
def setup(app, broker):
    config = utils.get_config()
    config.broadcast_interval = 0.01
    config.mqtt_host = 'localhost'
    config.mqtt_port = broker['mqtt']
    config.history_topic = 'testcast/history'
    config.state_topic = 'testcast/state'

    service_status.setup(app)
    scheduler.setup(app)
    mqtt.setup(app)
    codec.setup(app)
    block_store.setup(app)
    global_store.setup(app)
    service_store.setup(app)
    connection.setup(app)
    commander.setup(app)
    synchronization.setup(app)
    controller.setup(app)


@pytest.fixture
async def synchronized(app, client):
    await service_status.wait_synchronized(app)


@pytest.fixture
def m_publish(app, mocker: MockerFixture):
    m = mocker.spy(mqtt, 'publish')
    return m


async def test_disabled(app, client, synchronized):
    app['config'].broadcast_interval = 0
    app['config'].isolated = False
    b = broadcaster.Broadcaster(app)
    with pytest.raises(repeater.RepeaterCancelled):
        await b.prepare()


async def test_broadcast_unsync(app, client, synchronized, m_publish: Mock):
    service_status.fget(app).synchronized_ev.clear()

    app['config'].isolated = False
    b = broadcaster.Broadcaster(app)
    await b.prepare()
    await b.run()
    assert m_publish.call_count == 1


async def test_broadcast(app, client, synchronized, m_publish: Mock):
    app['config'].isolated = False

    b = broadcaster.Broadcaster(app)
    await b.prepare()
    await b.run()

    m_publish.assert_has_calls([
        call(app,
             topic='testcast/history/test_app',
             payload=ANY,
             err=False,
             ),
        call(app,
             topic='testcast/state/test_app',
             payload=ANY,
             retain=True,
             err=False,
             ),
    ])

    await b.before_shutdown(app)


async def test_error(app, client, synchronized, m_publish: Mock):
    app['config'].isolated = False
    b = broadcaster.Broadcaster(app)
    await b.prepare()

    mock_connection.NEXT_ERROR.append(ErrorCode.UNKNOWN_ERROR)
    with pytest.raises(exceptions.CommandException):
        await b.run()

    # Error over, resume normal work
    # 1 * only state event
    # 1 * history + state
    await b.run()
    assert m_publish.call_count == 3


async def test_api_broadcaster(app, client, m_publish: Mock):
    await service_status.wait_synchronized(app)
    app['config'].isolated = False
    b = broadcaster.Broadcaster(app)
    await b.prepare()
    await b.run()
    assert m_publish.call_count == 2
