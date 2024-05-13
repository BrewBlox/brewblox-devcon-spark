import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
from unittest.mock import AsyncMock, call

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI

from brewblox_devcon_spark import mqtt, utils
from brewblox_devcon_spark.connection import (connection_handler,
                                              mqtt_connection)

TESTED = mqtt_connection.__name__


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mqtt.lifespan():
        yield


@pytest.fixture
def app() -> FastAPI:
    mqtt.setup()
    mqtt_connection.setup()

    return FastAPI(lifespan=lifespan)


@pytest.fixture(autouse=True)
async def manager(manager: LifespanManager):
    yield manager


async def test_mqtt_discovery():
    config = utils.get_config()
    config.discovery_timeout_mqtt = timedelta(milliseconds=100)

    mqtt_client = mqtt.CV.get()
    recv = asyncio.Event()

    @mqtt_client.subscribe('brewcast/cbox/handshake/#')
    async def recv_cb(client, topic, payload, qos, properties):
        recv.set()

    # Publish handshake message
    mqtt_client.publish(f'brewcast/cbox/handshake/{config.device_id}',
                        'handshake message')
    await recv.wait()

    conn = await mqtt_connection.discover_mqtt(AsyncMock())
    assert isinstance(conn, mqtt_connection.MqttConnection)

    # If device ID is not set, we can't discover
    device_id = config.device_id
    config.device_id = None
    assert await mqtt_connection.discover_mqtt(AsyncMock()) is None
    config.device_id = device_id

    # Publish LWT -> controller disconnected
    recv.clear()
    mqtt_client.publish(f'brewcast/cbox/handshake/{config.device_id}', None)
    await recv.wait()

    # No longer discoverable
    assert await mqtt_connection.discover_mqtt(AsyncMock()) is None


async def test_mqtt_impl():
    callbacks = AsyncMock(spec=connection_handler.ConnectionHandler)
    config = utils.get_config()
    mqtt_client = mqtt.CV.get()

    recv_handshake = asyncio.Event()
    recv_req = asyncio.Event()
    recv_resp = asyncio.Event()
    recv_log = asyncio.Event()

    @mqtt_client.subscribe('brewcast/cbox/handshake/+')
    async def on_handshake(client, topic, payload, qos, properties):
        recv_handshake.set()

    @mqtt_client.subscribe('brewcast/cbox/req/+')
    async def on_request(client, topic, payload: bytes, qos, properties):
        resp_topic = topic.replace('/req/', '/resp/')
        mqtt_client.publish(resp_topic, f'1:0:{payload.decode()[::-1]}\n'.encode())
        recv_req.set()

    @mqtt_client.subscribe('brewcast/cbox/resp/+')
    async def on_response(client, topic, payload, qos, properties):
        recv_resp.set()

    @mqtt_client.subscribe('brewcast/cbox/log/+')
    async def on_log(client, topic, payload, qos, properties):
        recv_log.set()

    mqtt_client.publish(f'brewcast/cbox/handshake/{config.device_id}',
                        'handshake message')

    impl = mqtt_connection.MqttConnection(config.device_id, callbacks)
    await impl.connect()
    assert impl.connected.is_set()

    await impl.send_request('hello')
    await asyncio.wait_for(recv_req.wait(), timeout=5)
    await asyncio.wait_for(recv_resp.wait(), timeout=5)
    callbacks.on_response.assert_awaited_once_with('olleh')

    mqtt_client.publish(f'brewcast/cbox/log/{config.device_id}',
                        'log message')

    await asyncio.wait_for(recv_log.wait(), timeout=5)
    callbacks.on_event.assert_awaited_once_with('log message')

    # LWT is an empty message to handshake topic
    recv_handshake.clear()
    mqtt_client.publish(f'brewcast/cbox/handshake/{config.device_id}',
                        None)
    await asyncio.wait_for(recv_handshake.wait(), timeout=5)
    assert impl.disconnected.is_set()

    # Can safely be called
    await impl.close()
    assert impl.disconnected.is_set()


async def test_mqtt_message_handling():
    callbacks = AsyncMock(spec=connection_handler.ConnectionHandler)
    impl = mqtt_connection.MqttConnection('1234', callbacks)

    await impl._resp_cb(None, None, '1:0:first,'.encode(), 0, None)
    await impl._resp_cb(None, None, '2:1:second,'.encode(), 0, None)
    await impl._resp_cb(None, None, '3:1:third\n'.encode(), 0, None)
    await impl._resp_cb(None, None, '4:0:fourth\n'.encode(), 0, None)
    await impl._resp_cb(None, None, '5:0:fifth,'.encode(), 0, None)
    await impl._resp_cb(None, None, '5:1:fifth-second\n'.encode(), 0, None)
    await impl._resp_cb(None, None, '6:0:sixth,'.encode(), 0, None)
    await impl._resp_cb(None, None, 'garbled'.encode(), 0, None)
    await impl._resp_cb(None, None, '6:1:sixth-second\n'.encode(), 0, None)

    assert callbacks.on_response.await_args_list == [call('fourth'), call('fifth,fifth-second')]
