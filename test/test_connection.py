"""
Tests brewblox_devcon_spark.connection
"""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from brewblox_service import scheduler

from brewblox_devcon_spark import (connect_funcs, connection, exceptions,
                                   service_status, service_store)

TESTED = connection.__name__


class DummyExit(Exception):
    pass


@pytest.fixture(autouse=True)
def m_exit(mocker):
    mocker.patch(TESTED + '.web.GracefulExit', DummyExit)


@pytest.fixture(autouse=True)
def m_interval(mocker):
    mocker.patch(TESTED + '.BASE_RETRY_INTERVAL_S', 0.001)


@pytest.fixture
def m_reader(event_loop):
    return asyncio.StreamReader(loop=event_loop)


@pytest.fixture
def m_writer(event_loop):
    m = Mock()
    m.drain = AsyncMock()
    m.is_closing.return_value = False
    return m


@pytest.fixture
def m_connect(mocker, m_reader, m_writer):
    m = mocker.patch(TESTED + '.connect_funcs.connect', autospec=True)
    m.return_value = connect_funcs.ConnectionResult(
        host='localhost',
        port='8332',
        address='/dev/ttyACM0',
        process=Mock(),
        reader=m_reader,
        writer=m_writer,
    )
    return m


@pytest.fixture
def welcome():
    return [
        'BREWBLOX',
        'ed70d66f0',
        '3f2243a',
        '2019-06-18',
        '2019-06-18',
        '1.2.1-rc.2',
        'p1',
        '78',
        '0A',
        '1234567F0CASE'
    ]


@pytest.fixture
async def cbox_err():
    return [
        'CBOXERROR',
        '0C',
    ]


@pytest.fixture
def app(app, m_connect):
    service_status.setup(app)
    scheduler.setup(app)
    service_store.setup(app)
    return app


@pytest.fixture
def init_app(app):
    connection.setup(app)
    return app


async def test_write(app, init_app, client, m_writer):
    service_status.set_enabled(app, True)
    await asyncio.sleep(0.01)
    conn = connection.fget(app)
    assert conn.connected
    assert service_status.desc(app).connection_status == 'CONNECTED'
    assert service_status.desc(app).connection_kind == 'USB'

    await conn.write('testey')
    m_writer.write.assert_called_once_with(b'testey\n')
    m_writer.drain.assert_awaited_once()

    m_writer.reset_mock()
    await conn.write(b'testey')
    m_writer.write.assert_called_once_with(b'testey\n')
    m_writer.drain.assert_awaited_once()

    await conn.start_reconnect()
    m_writer.close.assert_called_once()

    m_writer.is_closing.return_value = True
    assert not conn.connected

    await conn.start_reconnect()
    m_writer.close.assert_called_once()

    with pytest.raises(exceptions.NotConnected):
        await conn.write('stuff')


async def test_sim_status(app, init_app, client, m_connect):
    app['config']['simulation'] = True
    service_status.set_enabled(app, True)
    await asyncio.sleep(0.01)
    assert service_status.desc(app).connection_kind == 'SIMULATION'


async def test_callback(app, init_app, client, m_reader, m_writer):
    service_status.set_enabled(app, True)
    await asyncio.sleep(0.01)
    conn = connection.fget(app)
    m_data_cb = AsyncMock()
    m_data_cb2 = AsyncMock()

    conn.data_callbacks.add(m_data_cb)
    conn.data_callbacks.add(m_data_cb2)

    m_reader.feed_data('<!connected:sensor>bunnies<fluffy>\n'.encode())
    await asyncio.sleep(0.01)
    m_data_cb.assert_awaited_with('bunnies')
    m_data_cb2.assert_awaited_with('bunnies')

    # Close it down
    m_reader.feed_data('puppies\n'.encode())
    m_writer.is_closing.return_value = True

    await asyncio.sleep(0.01)
    m_data_cb.assert_awaited_with('puppies')
    m_data_cb2.assert_awaited_with('puppies')
    assert conn.active
    assert not conn.connected
    assert service_status.desc(app).connection_status == 'DISCONNECTED'


async def test_error_callback(app, init_app, client, m_reader, m_writer):
    service_status.set_enabled(app, True)
    conn = connection.fget(app)
    m_data_cb = AsyncMock(side_effect=RuntimeError)
    conn.data_callbacks.add(m_data_cb)

    m_reader.feed_data('<!connected:sensor>bunnies<fluffy>\n'.encode())
    await asyncio.sleep(0.01)
    m_data_cb.assert_awaited_with('bunnies')
    assert conn.connected


@pytest.mark.filterwarnings('ignore:Handshake error')
async def test_on_welcome(app, init_app, client, mocker, welcome):
    mocker.patch(TESTED + '.web.GracefulExit', DummyExit)
    conn = connection.fget(app)
    status = service_status.fget(app)
    status.set_enabled(True)

    ok_msg = ','.join(welcome)
    nok_welcome = welcome.copy()
    nok_welcome[2] = 'NOPE'
    nok_msg = ','.join(nok_welcome)
    await conn._on_event(ok_msg)
    assert status.desc().firmware_error == 'MISMATCHED'
    status.status_desc.service.device.device_id = '1234567f0case'
    await conn._on_event(ok_msg)
    assert status.desc().identity_error is None

    status.status_desc.service.device.device_id = '01345'
    with pytest.warns(UserWarning, match='Handshake error'):
        await conn._on_event(ok_msg)
    assert status.desc().identity_error == 'INCOMPATIBLE'

    status.status_desc.service.device.device_id = ''
    app['config']['skip_version_check'] = True
    await conn._on_event(nok_msg)
    assert status.desc().identity_error == 'WILDCARD_ID'

    app['config']['skip_version_check'] = False
    with pytest.warns(UserWarning, match='Handshake error'):
        await conn._on_event(nok_msg)
    assert status.desc().identity_error == 'WILDCARD_ID'
    assert status.desc().connection_status == 'ACKNOWLEDGED'

    with pytest.raises(DummyExit):
        await conn._on_event(connection.SETUP_MODE_PREFIX)


async def test_on_cbox_err(app, init_app, client, cbox_err):
    conn = connection.fget(app)
    status = service_status.fget(app)
    status.set_connected('addr')
    assert status.desc().address == 'addr'

    msg = ':'.join(cbox_err)
    await conn._on_event(msg)

    # shouldn't fail on non-existent error message
    msg = ':'.join([cbox_err[0], 'ffff'])
    await conn._on_event(msg)

    # shouldn't fail on invalid error
    msg = ':'.join([cbox_err[0], 'not hex'])
    await conn._on_event(msg)


async def test_retry_exhausted(app, client, m_connect, m_writer, mocker):
    mocker.patch(TESTED + '.CONNECT_RETRY_COUNT', 2)
    m_connect.side_effect = ConnectionRefusedError

    service_status.set_enabled(app, True)
    conn = connection.SparkConnection(app)

    await conn.prepare()
    # count == 0
    with pytest.raises(ConnectionError):
        await conn.run()

    # count == 1
    with pytest.raises(ConnectionError):
        await conn.run()

    # count == 2 (and >= CONNECT_RETRY_COUNT)
    with pytest.raises(DummyExit):
        await conn.run()


async def test_discovery_abort(app, client, m_connect, mocker):
    mocker.patch(TESTED + '.CONNECT_RETRY_COUNT', 1)
    service_status.set_enabled(app, True)
    conn = connection.SparkConnection(app)
    await conn.prepare()

    m_connect.side_effect = connect_funcs.DiscoveryAbortedError(False)
    with pytest.raises(connect_funcs.DiscoveryAbortedError):
        await conn.run()

    m_connect.side_effect = connect_funcs.DiscoveryAbortedError(True)
    with pytest.raises(connect_funcs.DiscoveryAbortedError):
        await conn.run()

    with pytest.raises(DummyExit):
        await conn.run()
