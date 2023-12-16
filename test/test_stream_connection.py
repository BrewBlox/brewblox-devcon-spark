"""
Tests brewblox_devcon_spark.connection.stream_connection.py
"""

import asyncio
from typing import Generator

import pytest
from pytest_mock import MockerFixture

from brewblox_devcon_spark import utils
from brewblox_devcon_spark.connection import stream_connection
from brewblox_devcon_spark.mdns import ConnectInfo

TESTED = stream_connection.__name__


class EchoServerProtocol(asyncio.Protocol):
    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport

    def data_received(self, data: bytes) -> None:
        msg = data.decode()
        if 'error' in msg:
            self.transport.write_eof()
            return
        self.transport.write(f'{msg}<event>'.encode())


class DummyCallbacks(stream_connection.ConnectionCallbacks):
    def __init__(self) -> None:
        self.event_msg = None
        self.event_ev = asyncio.Event()

        self.response_msg = None
        self.response_ev = asyncio.Event()

    async def on_event(self, msg: str):
        self.event_msg = msg
        self.event_ev.set()

    async def on_response(self, msg: str):
        self.response_msg = msg
        self.response_ev.set()


@pytest.fixture
def random_port() -> int:
    return utils.get_free_port()


@pytest.fixture(autouse=True)
async def echo_server(random_port: int) -> Generator[asyncio.Server, None, None]:
    loop = asyncio.get_running_loop()
    server = await loop.create_server(EchoServerProtocol, 'localhost', random_port)
    async with server:
        async with utils.task_context(server.serve_forever()):
            yield server


async def test_tcp_connection(random_port: int):
    callbacks = DummyCallbacks()
    impl = await stream_connection.connect_tcp(callbacks, 'localhost', random_port)

    await impl.send_request('hello')
    await callbacks.response_ev.wait()
    await callbacks.event_ev.wait()
    assert callbacks.response_msg == 'hello'
    assert callbacks.event_msg == 'event'

    callbacks.response_ev.clear()
    callbacks.event_ev.clear()

    await impl.send_request('world')
    await callbacks.response_ev.wait()
    await callbacks.event_ev.wait()
    assert callbacks.response_msg == 'world'
    assert callbacks.event_msg == 'event'


async def test_tcp_connection_close(random_port: int):
    callbacks = DummyCallbacks()
    impl = await stream_connection.connect_tcp(callbacks, 'localhost', random_port)
    await impl.close()
    await asyncio.wait_for(impl.disconnected.wait(), timeout=5)
    await impl.close()  # Can safely be called again


async def test_tcp_connection_error(random_port: int):
    callbacks = DummyCallbacks()
    impl = await stream_connection.connect_tcp(callbacks, 'localhost', random_port)
    await impl.send_request('error')
    await asyncio.wait_for(impl.disconnected.wait(), timeout=5)


async def test_discover_mdns(mocker: MockerFixture, random_port: int):
    config = utils.get_config()

    m_mdns_discover = mocker.patch(TESTED + '.mdns.discover_one', autospec=True)
    m_mdns_discover.return_value = ConnectInfo('localhost', random_port, config.device_id)
    callbacks = DummyCallbacks()
    impl = await stream_connection.discover_mdns(callbacks)

    await impl.send_request('mdns')
    await callbacks.response_ev.wait()
    await callbacks.event_ev.wait()
    assert callbacks.response_msg == 'mdns'
    assert callbacks.event_msg == 'event'


async def test_discover_mdns_none(mocker: MockerFixture):
    m_mdns_discover = mocker.patch(TESTED + '.mdns.discover_one', autospec=True)
    m_mdns_discover.side_effect = asyncio.TimeoutError
    callbacks = DummyCallbacks()
    assert await stream_connection.discover_mdns(callbacks) is None
