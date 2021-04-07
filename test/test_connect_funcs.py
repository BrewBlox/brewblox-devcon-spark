"""
Tests brewblox_devcon_spark.connect_funcs
"""

import asyncio
from collections import namedtuple

import pytest
from brewblox_service import http
from mock import AsyncMock, Mock

from brewblox_devcon_spark import connect_funcs, exceptions
from brewblox_devcon_spark.connect_funcs import ConnectionResult

TESTED = connect_funcs.__name__

DummyPortInfo = namedtuple('DummyPortInfo', ['device', 'description', 'hwid', 'serial_number'])


@pytest.fixture(autouse=True)
def m_sleep(mocker):
    mocker.patch(TESTED + '.DISCOVERY_INTERVAL_S', 0.001)
    mocker.patch(TESTED + '.DISCOVERY_DNS_TIMEOUT_S', 1)
    mocker.patch(TESTED + '.SUBPROCESS_CONNECT_INTERVAL_S', 0.001)


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
def m_popen(mocker):
    m = mocker.patch(TESTED + '.subprocess.Popen')
    m.return_value.poll.return_value = None
    return m


@pytest.fixture
def m_connect(mocker, m_reader, m_writer):
    m = mocker.patch(TESTED + '.asyncio.open_connection', AsyncMock())
    m.return_value = (m_reader, m_writer)
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


async def test_connect_simulation(app, client, m_reader, m_writer, m_popen, m_connect):
    # --simulation is set -> create subprocess and connect to it
    # --device-host / --device-serial are ignored
    app['config']['simulation'] = True
    app['config']['device_serial'] = '/dev/ttyACM0'
    app['config']['device_host'] = 'testey'
    app['config']['device_port'] = 1234

    expected = ConnectionResult(
        host='localhost',
        port=8332,
        # We assume that tests are always run on an AMD64 host
        address='brewblox-amd64.sim',
        process=m_popen.return_value,
        reader=m_reader,
        writer=m_writer
    )

    assert (await connect_funcs.connect(app)) == expected
    m_connect.assert_awaited_once_with('localhost', 8332)


async def test_connect_simulation_unsupported(app, client, mocker):
    app['config']['simulation'] = True

    m_machine = mocker.patch(TESTED + '.platform.machine')
    m_machine.return_value = 'anthill_inside'

    with pytest.raises(exceptions.ConnectionImpossible):
        await connect_funcs.connect_simulation(app)


async def test_connect_tcp(app, client, m_reader, m_writer, m_connect):
    # --device-host is set -> directly connect to TCP address
    app['config']['simulation'] = False
    app['config']['device_serial'] = None
    app['config']['device_host'] = 'testey'
    app['config']['device_port'] = 1234

    expected = ConnectionResult(
        host='testey',
        port=1234,
        address='testey:1234',
        process=None,
        reader=m_reader,
        writer=m_writer
    )

    assert (await connect_funcs.connect(app)) == expected
    m_connect.assert_awaited_once_with('testey', 1234)


async def test_connect_serial(app, client, m_reader, m_writer, m_popen, m_connect):
    # --device-serial is set -> directly connect to USB device
    app['config']['simulation'] = False
    app['config']['device_serial'] = '/dev/testey'
    app['config']['device_host'] = 'testey'
    app['config']['device_port'] = 1234

    expected = ConnectionResult(
        host='localhost',
        port=8332,
        address='/dev/testey',
        process=m_popen.return_value,
        reader=m_reader,
        writer=m_writer
    )

    assert (await connect_funcs.connect(app)) == expected
    m_connect.assert_awaited_once_with('localhost', 8332)


async def test_connect_subprocess(app, client, m_reader, m_writer, m_connect, m_popen, mocker):
    mocker.patch(TESTED + '.SUBPROCESS_CONNECT_RETRY_COUNT', 2)
    proc = m_popen.return_value
    address = '/dev/testey'

    # Happiest flow: open_connection() immediately works
    expected = ConnectionResult(
        host='localhost',
        port=8332,
        address=address,
        process=proc,
        reader=m_reader,
        writer=m_writer
    )
    assert (await connect_funcs.connect_subprocess(proc, address)) == expected

    # Happy flow: open_connection() returns an error, but retry works
    m_connect.side_effect = [
        ConnectionRefusedError(),
        (m_reader, m_writer)
    ]
    assert (await connect_funcs.connect_subprocess(proc, address)) == expected

    # Unhappy flow: open_connection() is unable to establish connection
    m_connect.side_effect = ChildProcessError('message')
    with pytest.raises(ConnectionError, match=r'ChildProcessError\(message\)'):
        await connect_funcs.connect_subprocess(proc, address)
    assert proc.terminate.call_count == 1

    # Unhappy flow: subprocess died
    proc.poll.return_value = 123
    proc.returncode = 123
    with pytest.raises(ChildProcessError, match=r'Subprocess exited with return code 123'):
        await connect_funcs.connect_subprocess(proc, address)


async def test_discover_serial(app, client, m_reader, m_writer, m_popen, m_connect):
    # --device-serial and --device-host are not set
    # --discovery=usb -> discovery is restricted to USB
    app['config']['simulation'] = False
    app['config']['device_serial'] = None
    app['config']['device_host'] = None
    app['config']['device_port'] = 1234
    app['config']['device_id'] = None
    app['config']['discovery'] = 'usb'

    expected = ConnectionResult(
        host='localhost',
        port=8332,
        address='/dev/ttyX',
        process=m_popen.return_value,
        reader=m_reader,
        writer=m_writer
    )

    # We always end up connecting to localhost:8332, regardless of port
    assert (await connect_funcs.connect(app)) == expected

    expected = ConnectionResult(
        host='localhost',
        port=8332,
        address='/dev/ttyY',
        process=m_popen.return_value,
        reader=m_reader,
        writer=m_writer
    )

    # Filter by device ID
    # We still connect to localhost:8332, but address is now /dev/ttyY
    app['config']['device_id'] = '4321BA'
    m_popen.reset_mock()
    assert (await connect_funcs.connect(app)) == expected

    # Not found
    app['config']['device_id'] = 'pancakes'
    with pytest.raises(connect_funcs.DiscoveryAbortedError):
        await connect_funcs.connect(app)


async def test_discover_tcp(app, client, m_mdns, m_reader, m_writer, m_connect):
    # --device-serial and --device-host are not set
    # --discovery=wifi -> USB discovery is skipped
    app['config']['simulation'] = False
    app['config']['device_serial'] = None
    app['config']['device_host'] = None
    app['config']['device_port'] = 1234
    app['config']['device_id'] = None
    app['config']['discovery'] = 'wifi'

    # host/port values are defined in the m_dns fixture
    expected = ConnectionResult(
        host='enterprise',
        port=5678,
        address='enterprise:5678',
        process=None,
        reader=m_reader,
        writer=m_writer
    )

    assert (await connect_funcs.connect(app)) == expected

    # unreachable mDNS service
    m_mdns.side_effect = asyncio.TimeoutError
    with pytest.raises(connect_funcs.DiscoveryAbortedError):
        await connect_funcs.connect(app)
