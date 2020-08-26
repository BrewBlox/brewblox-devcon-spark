"""
Tests brewblox_devcon_spark.connection
"""

import asyncio
from collections import namedtuple

import pytest
from brewblox_service import http
from mock import AsyncMock, Mock

from brewblox_devcon_spark import connection

TESTED = connection.__name__

DummyPortInfo = namedtuple('DummyPortInfo', ['device', 'description', 'hwid', 'serial_number'])


class DummyExit(Exception):
    pass


@pytest.fixture(autouse=True)
def m_sleep(mocker):
    mocker.patch(TESTED + '.DISCOVER_INTERVAL_S', 0.001)
    mocker.patch(TESTED + '.DNS_DISCOVER_TIMEOUT_S', 1)


@pytest.fixture(autouse=True)
def m_exit(mocker):
    mocker.patch(TESTED + '.web.GracefulExit', DummyExit)


@pytest.fixture
def m_reader(loop):
    return asyncio.StreamReader(loop=loop)


@pytest.fixture
def m_writer():
    m = Mock()
    m.write = AsyncMock()
    m.transport = Mock()
    return m


@pytest.fixture
def m_connect_serial(mocker, m_reader, m_writer):
    m = mocker.patch(TESTED + '.open_serial_connection', AsyncMock())
    m.return_value = (m_reader, m_writer)
    return m


@pytest.fixture
def m_connect_tcp(mocker, m_reader, m_writer):
    m = mocker.patch(TESTED + '.asyncio.open_connection', AsyncMock())
    m.return_value = (m_reader, m_writer)
    return m


@pytest.fixture(autouse=True)
def m_comports(mocker):
    m = mocker.patch(TESTED + '.list_ports.comports')
    m.return_value = [
        DummyPortInfo('/dev/dummy', 'Dummy', 'USB VID:PID=1a02:b123', '1234AB'),
        DummyPortInfo('/dev/ttyX', 'Electron', 'USB VID:PID=2d04:c00a', '4321BA'),
        DummyPortInfo('/dev/ttyY', 'Electron', 'USB VID:PID=2d04:c00a', '4321BA'),
    ]
    return m


@pytest.fixture(autouse=True)
def m_grep_ports(mocker):
    m = mocker.patch(TESTED + '.list_ports.grep')
    m.return_value = [
        DummyPortInfo('/dev/ttyX', 'Electron', 'USB VID:PID=2d04:c00a', '1234AB'),
        DummyPortInfo('/dev/ttyY', 'Electron', 'USB VID:PID=2d04:c00a', '4321BA'),
    ]
    return m


@pytest.fixture
async def m_mdns(app, loop, mocker):
    m_discover = mocker.patch(TESTED + '.mdns.discover_one', AsyncMock())
    m_discover.return_value = ('enterprise', 5678, None)
    return m_discover


@pytest.fixture
def app(app):
    http.setup(app)
    return app


async def test_connect_tcp(app, client, m_reader, m_writer, m_connect_tcp):
    app['config']['device_serial'] = None
    app['config']['device_host'] = 'testey'
    app['config']['device_port'] = 1234
    assert (await connection.connect(app)) == ('testey:1234', m_reader, m_writer)
    m_connect_tcp.assert_awaited_once_with('testey', 1234)


async def test_connect_serial(app, client, m_reader, m_writer, m_connect_serial):
    app['config']['device_serial'] = '/dev/testey'
    app['config']['device_host'] = 'testey'
    app['config']['device_port'] = 1234
    assert (await connection.connect(app)) == ('/dev/testey', m_reader, m_writer)
    m_connect_serial.assert_awaited_once_with(url='/dev/testey', baudrate=connection.DEFAULT_BAUD_RATE)


async def test_discover_serial(app, client, m_reader, m_writer, m_connect_serial):
    app['config']['device_serial'] = None
    app['config']['device_host'] = None
    app['config']['device_port'] = 1234
    app['config']['device_id'] = None
    app['config']['discovery'] = 'usb'

    # First valid vid:pid
    assert (await connection.connect(app)) == ('/dev/ttyX', m_reader, m_writer)

    # Filtered by device ID
    app['config']['device_id'] = '4321BA'
    assert (await connection.connect(app)) == ('/dev/ttyY', m_reader, m_writer)

    # Not found
    app['config']['device_id'] = 'pancakes'
    with pytest.raises(DummyExit):
        await connection.connect(app)


async def test_discover_tcp(app, client, m_mdns, m_reader, m_writer, m_connect_tcp):
    app['config']['device_serial'] = None
    app['config']['device_host'] = None
    app['config']['device_port'] = 1234
    app['config']['device_id'] = None
    app['config']['discovery'] = 'wifi'

    assert (await connection.connect(app)) == ('enterprise:5678', m_reader, m_writer)

    # unreachable mDNS service
    m_mdns.side_effect = TimeoutError
    with pytest.raises(DummyExit):
        await connection.connect(app)
