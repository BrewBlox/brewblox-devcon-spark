"""
Tests brewblox_devcon_spark.connection
"""

import asyncio

import pytest
from brewblox_service import scheduler
from mock import AsyncMock, Mock

from brewblox_devcon_spark import (service_store, connect_funcs, connection,
                                   exceptions, service_status)

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
    m = mocker.patch(TESTED + '.connect_funcs.connect', AsyncMock())
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
    service_status.set_autoconnecting(app, True)
    await asyncio.sleep(0.01)
    conn = connection.fget(app)
    assert conn.connected
    assert service_status.desc(app).is_connected
    assert service_status.desc(app).connection_kind == 'usb'

    await conn.write('testey')
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
    service_status.set_autoconnecting(app, True)
    await asyncio.sleep(0.01)
    assert service_status.desc(app).connection_kind == 'simulation'


async def test_callback(app, init_app, client, m_reader, m_writer):
    service_status.set_autoconnecting(app, True)
    await asyncio.sleep(0.01)
    conn = connection.fget(app)
    m_data_cb = Mock()
    m_data_cb2 = Mock()

    conn.data_callbacks.add(m_data_cb)
    conn.data_callbacks.add(m_data_cb2)

    m_reader.feed_data('<!connected:sensor>bunnies<fluffy>\n'.encode())
    await asyncio.sleep(0.01)
    m_data_cb.assert_called_with('bunnies')
    m_data_cb2.assert_called_with('bunnies')

    # Close it down
    m_reader.feed_data('puppies\n'.encode())
    m_writer.is_closing.return_value = True

    await asyncio.sleep(0.01)
    m_data_cb.assert_called_with('puppies')
    m_data_cb2.assert_called_with('puppies')
    assert conn.active
    assert not conn.connected
    assert not service_status.desc(app).is_connected


async def test_error_callback(app, init_app, client, m_reader, m_writer):
    service_status.set_autoconnecting(app, True)
    conn = connection.fget(app)
    m_data_cb = Mock(side_effect=RuntimeError)
    conn.data_callbacks.add(m_data_cb)

    m_reader.feed_data('<!connected:sensor>bunnies<fluffy>\n'.encode())
    await asyncio.sleep(0.01)
    m_data_cb.assert_called_with('bunnies')
    assert conn.connected


async def test_on_welcome(app, init_app, client, mocker, welcome):
    conn = connection.fget(app)
    status = service_status.fget(app)
    status.set_autoconnecting(True)

    ok_msg = ','.join(welcome)
    nok_welcome = welcome.copy()
    nok_welcome[2] = 'NOPE'
    nok_msg = ','.join(nok_welcome)
    conn._on_event(ok_msg)
    assert status.desc().handshake_info.is_compatible_firmware

    status.service_info.device_id = '1234567f0case'
    conn._on_event(ok_msg)
    assert status.desc().handshake_info.is_valid_device_id

    status.service_info.device_id = '01345'
    with pytest.warns(UserWarning, match='Handshake error'):
        conn._on_event(ok_msg)
    assert not status.desc().handshake_info.is_valid_device_id

    status.service_info.device_id = None
    app['config']['skip_version_check'] = True
    conn._on_event(nok_msg)
    assert status.desc().handshake_info.is_compatible_firmware

    app['config']['skip_version_check'] = False
    with pytest.warns(UserWarning, match='Handshake error'):
        conn._on_event(nok_msg)
    assert not status.desc().handshake_info.is_compatible_firmware
    assert not status.desc().is_synchronized


async def test_on_cbox_err(app, init_app, client, cbox_err):
    conn = connection.fget(app)
    status = service_status.fget(app)
    status.set_connected('addr')
    assert status.desc().device_address == 'addr'

    msg = ':'.join(cbox_err)
    conn._on_event(msg)

    # shouldn't fail on non-existent error message
    msg = ':'.join([cbox_err[0], 'ffff'])
    conn._on_event(msg)

    # shouldn't fail on invalid error
    msg = ':'.join([cbox_err[0], 'not hex'])
    conn._on_event(msg)


async def test_on_setup_mode(app, init_app, client, m_exit):
    conn = connection.fget(app)
    with pytest.raises(DummyExit):
        conn._on_event('SETUP_MODE')


async def test_retry_exhausted(app, client, m_writer, mocker):
    mocker.patch(TESTED + '.CONNECT_RETRY_COUNT', 2)
    mocker.patch(TESTED + '.connect_funcs.connect', AsyncMock(side_effect=ConnectionRefusedError))

    service_status.set_autoconnecting(app, True)
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
    service_status.set_autoconnecting(app, True)
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
