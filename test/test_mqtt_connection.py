"""
Tests brewblox_devcon_spark.connection.mqtt_connection
"""

from unittest.mock import AsyncMock

import pytest

from brewblox_devcon_spark.connection import (connection_handler,
                                              mqtt_connection)

TESTED = mqtt_connection.__name__


@pytest.fixture
async def m_mqtt(mocker):
    return {
        k: mocker.patch(f'{TESTED}.mqtt.{k}', autospec=True)
        for k in [
            'listen',
            'subscribe',
            'unlisten',
            'unsubscribe',
            'publish'
        ]}


@pytest.fixture
async def app(app, m_mqtt):
    app['config']['isolated'] = False
    mqtt_connection.setup(app)
    return app


async def test_mqtt_discovery(app, client, m_mqtt, mocker):
    mocker.patch(TESTED + '.DISCOVERY_TIMEOUT_S', 0.001)
    device_id = app['config']['device_id']

    tracker = mqtt_connection.fget(app)
    await tracker._handshake_cb(mqtt_connection.HANDSHAKE_TOPIC + device_id, 'handshake message')

    assert await tracker.discover(AsyncMock(), None) is None
    assert await tracker.discover(AsyncMock(), '09876') is None

    conn = await tracker.discover(AsyncMock(), device_id)
    assert isinstance(conn, mqtt_connection.MqttConnection)

    conn = await mqtt_connection.discover_mqtt(app, AsyncMock())
    assert isinstance(conn, mqtt_connection.MqttConnection)

    # LWT received: controller disconnected
    await tracker._handshake_cb(mqtt_connection.HANDSHAKE_TOPIC + device_id, '')
    assert await tracker.discover(AsyncMock(), device_id) is None


async def test_mqtt_impl(app, client, m_mqtt, mocker):
    callbacks = AsyncMock(spec=connection_handler.ConnectionHandler(app))
    device_id = app['config']['device_id']
    impl = mqtt_connection.MqttConnection(app, device_id, callbacks)
    await impl.connect()
    assert impl.connected.is_set()
    assert m_mqtt['subscribe'].await_count == 1 + 3  # includes initial call by tracker
    assert m_mqtt['listen'].await_count == 1 + 3  # includes initial call by tracker

    await impl.send_request('hello')
    m_mqtt['publish'].assert_awaited_once_with(app, mqtt_connection.REQUEST_TOPIC + device_id, 'hello')

    await impl._resp_cb('topic', 'resp')
    callbacks.on_response.assert_awaited_once_with('resp')

    await impl._log_cb('topic', 'event')
    callbacks.on_event.assert_awaited_once_with('event')

    # LWT is an empty message to handshake topic
    await impl._handshake_cb('topic', 'republish')
    assert not impl.disconnected.is_set()
    await impl._handshake_cb('topic', '')
    assert impl.disconnected.is_set()

    # Can safely be called
    await impl.close()
    assert impl.disconnected.is_set()
    assert m_mqtt['unsubscribe'].await_count == 3
    assert m_mqtt['unlisten'].await_count == 3
