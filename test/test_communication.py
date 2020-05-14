"""
Tests brewblox_devcon_spark.communication
"""

import asyncio

import pytest
from brewblox_service import scheduler
from mock import AsyncMock, Mock

from brewblox_devcon_spark import communication, exceptions, state

TESTED = communication.__name__


class DummyExit(Exception):
    pass


@pytest.fixture(autouse=True)
def m_exit(mocker):
    mocker.patch(TESTED + '.web.GracefulExit', DummyExit)


@pytest.fixture(autouse=True)
def m_interval(mocker):
    mocker.patch(TESTED + '.RETRY_INTERVAL_S', 0.001)


@pytest.fixture
def m_reader(loop):
    return asyncio.StreamReader(loop=loop)


@pytest.fixture
def m_writer(loop):
    m = Mock()
    m.drain = AsyncMock()
    m.is_closing.return_value = False
    return m


@pytest.fixture
def m_connect(mocker, m_reader, m_writer):
    m = mocker.patch(TESTED + '.connection.connect', AsyncMock())
    m.return_value = ('addr', m_reader, m_writer)
    return m


@pytest.fixture
def app(app, m_connect):
    state.setup(app)
    scheduler.setup(app)
    return app


@pytest.fixture
def init_app(app):
    communication.setup(app)
    return app


async def test_write(init_app, client, m_writer):
    await state.set_autoconnecting(init_app, True)
    await asyncio.sleep(0.01)
    conduit = communication.get_conduit(init_app)
    assert conduit.connected
    assert state.summary(init_app).connect

    await conduit.write('testey')
    m_writer.write.assert_called_once_with(b'testey\n')
    m_writer.drain.assert_awaited_once()

    m_writer.is_closing.return_value = True
    assert not conduit.connected

    with pytest.raises(exceptions.NotConnected):
        await conduit.write('stuff')


async def test_callback(init_app, client, m_reader, m_writer):
    await state.set_autoconnecting(init_app, True)
    await asyncio.sleep(0.01)
    conduit = communication.get_conduit(init_app)
    m_event_cb = AsyncMock()
    m_data_cb = AsyncMock()
    m_data_cb2 = AsyncMock()

    conduit.event_callbacks.add(m_event_cb)
    conduit.data_callbacks.add(m_data_cb)
    conduit.data_callbacks.add(m_data_cb2)

    m_reader.feed_data('<!connected:sensor>bunnies<fluffy>\n'.encode())
    await asyncio.sleep(0.01)
    m_event_cb.assert_awaited_with(conduit, 'connected:sensor')
    m_data_cb.assert_awaited_with(conduit, 'bunnies')
    m_data_cb2.assert_awaited_with(conduit, 'bunnies')

    # Close it down
    m_reader.feed_data('puppies\n'.encode())
    m_writer.is_closing.return_value = True

    await asyncio.sleep(0.01)
    m_data_cb.assert_awaited_with(conduit, 'puppies')
    m_data_cb2.assert_awaited_with(conduit, 'puppies')
    assert conduit.active
    assert not conduit.connected
    assert not state.summary(init_app).connect


async def test_error_callback(init_app, client, m_reader, m_writer):
    await state.set_autoconnecting(init_app, True)
    conduit = communication.get_conduit(init_app)
    m_event_cb = AsyncMock(side_effect=RuntimeError)
    m_data_cb = AsyncMock()

    conduit.data_callbacks.add(m_data_cb)
    conduit.event_callbacks.add(m_event_cb)

    m_reader.feed_data('<!connected:sensor>bunnies<fluffy>\n'.encode())
    await asyncio.sleep(0.01)
    m_event_cb.assert_awaited_with(conduit, 'connected:sensor')
    m_data_cb.assert_awaited_with(conduit, 'bunnies')
    assert conduit.connected


async def test_retry_exhausted(app, client, m_writer, mocker):
    mocker.patch(TESTED + '.CONNECT_RETRY_COUNT', 2)
    mocker.patch(TESTED + '.connection.connect', AsyncMock(side_effect=ConnectionRefusedError))

    await state.set_autoconnecting(app, True)
    conduit = communication.SparkConduit(app)

    await conduit.prepare()
    # count == 0
    with pytest.raises(ConnectionError):
        await conduit.run()

    # count == 1
    with pytest.raises(ConnectionError):
        await conduit.run()

    # count == 2
    with pytest.raises(ConnectionError):
        await conduit.run()

    # count == 3 (and > CONNECT_RETRY_COUNT)
    with pytest.raises(DummyExit):
        await conduit.run()
