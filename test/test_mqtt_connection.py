"""
Tests brewblox_devcon_spark.connection.mqtt_connection
"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from brewblox_service import mqtt, scheduler

from brewblox_devcon_spark.connection import (connection_handler,
                                              mqtt_connection)
from brewblox_devcon_spark.models import ServiceConfig

TESTED = mqtt_connection.__name__


@pytest.fixture
async def setup(app, broker):
    config: ServiceConfig = app['config']
    config.isolated = False
    config.mqtt_host = 'localhost'
    config.mqtt_port = broker['mqtt']

    scheduler.setup(app)
    mqtt.setup(app)
    mqtt_connection.setup(app)


@pytest.fixture(autouse=True)
async def synchronized(app, client):
    await asyncio.wait_for(mqtt.fget(app).ready.wait(), timeout=5)


async def test_mqtt_discovery(app, client, mocker):
    mocker.patch(TESTED + '.DISCOVERY_TIMEOUT_S', 0.001)
    recv = asyncio.Event()
    config: ServiceConfig = app['config']
    device_id = config.device_id

    async def recv_cb(topic: str, payload: str):
        recv.set()

    await mqtt.listen(app, 'brewcast/cbox/handshake/#', recv_cb)

    # Publish handshake message
    await mqtt.publish(app,
                       topic=f'brewcast/cbox/handshake/{device_id}',
                       payload='handshake message')
    await recv.wait()

    tracker = mqtt_connection.fget(app)

    assert await tracker.discover(AsyncMock(), None) is None
    assert await tracker.discover(AsyncMock(), '09876') is None

    conn = await tracker.discover(AsyncMock(), device_id)
    assert isinstance(conn, mqtt_connection.MqttConnection)

    conn = await mqtt_connection.discover_mqtt(app, AsyncMock())
    assert isinstance(conn, mqtt_connection.MqttConnection)

    # Publish LWT -> controller disconnected
    recv.clear()
    await mqtt.publish(app,
                       topic=f'brewcast/cbox/handshake/{device_id}',
                       payload='')
    await recv.wait()

    # No longer discoverable
    assert await tracker.discover(AsyncMock(), device_id) is None


async def test_mqtt_impl(app, client, mocker):
    callbacks = AsyncMock(spec=connection_handler.ConnectionHandler(app))
    config: ServiceConfig = app['config']
    device_id = config.device_id
    recv_handshake = asyncio.Event()
    recv_req = asyncio.Event()
    recv_resp = asyncio.Event()
    recv_log = asyncio.Event()

    async def on_handshake(topic: str, payload: str):
        recv_handshake.set()

    async def on_request(topic: str, payload: str):
        resp_topic = topic.replace('/req/', '/resp/')
        await mqtt.publish(app, resp_topic, payload[::-1])
        recv_req.set()

    async def on_response(topic: str, payload: str):
        recv_resp.set()

    async def on_log(topic: str, payload: str):
        recv_log.set()

    await mqtt.subscribe(app, '#')
    await mqtt.listen(app, 'brewcast/cbox/handshake/#', on_handshake)
    await mqtt.listen(app, 'brewcast/cbox/req/#', on_request)
    await mqtt.listen(app, 'brewcast/cbox/resp/#', on_response)
    await mqtt.listen(app, 'brewcast/cbox/log/#', on_log)

    await mqtt.publish(app,
                       topic=f'brewcast/cbox/handshake/{device_id}',
                       payload='handshake message')

    impl = mqtt_connection.MqttConnection(app, device_id, callbacks)
    await impl.connect()
    assert impl.connected.is_set()

    await impl.send_request('hello')
    await asyncio.wait_for(recv_req.wait(), timeout=5)
    await asyncio.wait_for(recv_resp.wait(), timeout=5)
    callbacks.on_response.assert_awaited_once_with('olleh')

    await mqtt.publish(app,
                       topic=f'brewcast/cbox/log/{device_id}',
                       payload='log message')

    await asyncio.wait_for(recv_log.wait(), timeout=5)
    callbacks.on_event.assert_awaited_once_with('log message')

    # LWT is an empty message to handshake topic
    recv_handshake.clear()
    await mqtt.publish(app,
                       topic=f'brewcast/cbox/handshake/{device_id}',
                       payload='')
    await asyncio.wait_for(recv_handshake.wait(), timeout=5)
    assert impl.disconnected.is_set()

    # Can safely be called
    await impl.close()
    assert impl.disconnected.is_set()


async def test_isolated(app, client, mocker):
    m_listen = mocker.spy(mqtt, 'listen')
    m_unlisten = mocker.spy(mqtt, 'unlisten')
    app['config'].isolated = True

    tracker = mqtt_connection.MqttDeviceTracker(app)
    await tracker.startup(app)
    assert await tracker.discover(AsyncMock(), '1234') is None
    await tracker.before_shutdown(app)
    await tracker.shutdown(app)

    assert m_listen.await_count == 0
    assert m_unlisten.await_count == 0
