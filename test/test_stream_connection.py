"""
Tests brewblox_devcon_spark.connection.stream_connection.py
"""

import asyncio

import pytest

from brewblox_devcon_spark.connection import stream_connection
from brewblox_devcon_spark.mdns import ConnectInfo

TESTED = stream_connection.__name__


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
def test_port(find_free_port):
    return find_free_port()


@pytest.fixture
async def echo_server(test_port):
    async def echo_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        while True:
            data = await reader.read(100)
            if not data:
                break
            if data == b'error\n':
                writer.write_eof()
                break
            writer.write(data+b'<event>')
            await writer.drain()
        writer.close()
        await writer.wait_closed()
    server = await asyncio.start_server(echo_handler, 'localhost', test_port)
    task = asyncio.create_task(server.serve_forever())
    yield server
    task.cancel()


async def test_tcp_connection(app, client, echo_server, test_port):
    callbacks = DummyCallbacks()
    impl = await stream_connection.connect_tcp('localhost', test_port, callbacks)

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


async def test_tcp_connection_close(app, client, echo_server, test_port):
    callbacks = DummyCallbacks()
    impl = await stream_connection.connect_tcp('localhost', test_port, callbacks)
    await impl.close()
    await asyncio.wait_for(impl.disconnected.wait(), timeout=5)
    await impl.close()  # Can safely be called again


async def test_tcp_connection_error(app, client, echo_server, test_port):
    callbacks = DummyCallbacks()
    impl = await stream_connection.connect_tcp('localhost', test_port, callbacks)
    await impl.send_request('error')
    await asyncio.wait_for(impl.disconnected.wait(), timeout=5)


async def test_discover_tcp(app, client, echo_server, mocker, test_port):
    m_mdns_discover = mocker.patch(TESTED + '.mdns.discover_one', autospec=True)
    m_mdns_discover.return_value = ConnectInfo('localhost', test_port, app['config']['device_id'])
    callbacks = DummyCallbacks()
    impl = await stream_connection.discover_tcp(app, callbacks)

    await impl.send_request('mdns')
    await callbacks.response_ev.wait()
    await callbacks.event_ev.wait()
    assert callbacks.response_msg == 'mdns'
    assert callbacks.event_msg == 'event'


async def test_discover_tcp_none(app, client, mocker):
    m_mdns_discover = mocker.patch(TESTED + '.mdns.discover_one', autospec=True)
    m_mdns_discover.side_effect = asyncio.TimeoutError
    callbacks = DummyCallbacks()
    assert await stream_connection.discover_tcp(app, callbacks) is None
