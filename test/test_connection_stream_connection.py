import asyncio

import pytest
import pytest_asyncio
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


class Context:
    def __init__(self, loop, port):
        self.loop = loop
        self.port = port
        self.server = None

    async def start_server(self):
        """Start a server with the callback *handle_client* listening on
        "self.addr".
        """
        self.server = await self.loop.create_server(EchoServerProtocol, 'localhost', self.port)

    async def close_server(self):
        """Close the server."""
        if self.server is not None:
            server, self.server = self.server, None
            server.close()
            await server.wait_closed()


@pytest_asyncio.fixture(loop_scope='session', scope='session')
async def ctx(unused_tcp_port_factory):
    """Generate tests with TCP sockets and Unix domain sockets."""
    port = unused_tcp_port_factory()

    ctx = Context(asyncio.get_event_loop(), port)
    try:
        await ctx.start_server()
        yield ctx
    finally:
        # # Collect all tasks and cancel those that are not 'done'.
        tasks = asyncio.all_tasks(ctx.loop)
        tasks = [t for t in tasks if not t.done()]
        for task in tasks:
            task.cancel()

        # Wait for all tasks to complete, ignoring any CancelledErrors
        try:
            await asyncio.wait(tasks)
        except asyncio.exceptions.CancelledError:
            pass


@pytest.mark.asyncio(loop_scope='session')
async def test_tcp_connection(ctx):
    callbacks = DummyCallbacks()
    impl = await stream_connection.connect_tcp(callbacks, 'localhost', ctx.port)

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


@pytest.mark.asyncio(loop_scope='session')
async def test_tcp_connection_close(ctx):
    callbacks = DummyCallbacks()
    impl = await stream_connection.connect_tcp(callbacks, 'localhost', ctx.port)
    await impl.close()
    await asyncio.wait_for(impl.disconnected.wait(), timeout=5)
    await impl.close()  # Can safely be called again


@pytest.mark.asyncio(loop_scope='session')
async def test_tcp_connection_error(ctx):
    callbacks = DummyCallbacks()
    impl = await stream_connection.connect_tcp(callbacks, 'localhost', ctx.port)
    await impl.send_request('error')
    await asyncio.wait_for(impl.disconnected.wait(), timeout=5)


@pytest.mark.asyncio(loop_scope='session')
async def test_discover_mdns(mocker: MockerFixture, ctx):
    config = utils.get_config()

    m_mdns_discover = mocker.patch(TESTED + '.mdns.discover_one', autospec=True)
    m_mdns_discover.return_value = ConnectInfo('localhost', ctx.port, config.device_id)
    callbacks = DummyCallbacks()
    impl = await stream_connection.discover_mdns(callbacks)
    assert impl is not None

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
