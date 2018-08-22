"""
Tests brewblox_devcon_spark.communication
"""

import asyncio
from collections import namedtuple
from unittest.mock import Mock, call

import pytest
from asynctest import CoroutineMock
from brewblox_service import scheduler

from brewblox_devcon_spark import communication, exceptions, status

DummyPortInfo = namedtuple('DummyPortInfo', ['device', 'description', 'hwid', 'serial_number'])

TESTED = communication.__name__


class Collector():
    def __init__(self, loop):
        self.events = asyncio.Queue(loop=loop)
        self.data = asyncio.Queue(loop=loop)

    def on_event(self, e):
        self.events.put_nowait(e)

    def on_data(self, d):
        self.data.put_nowait(d)

    async def async_on_event(self, conduit, e):
        await self.events.put(e)

    async def async_on_data(self, conduit, d):
        await self.data.put(d)

    async def _verify(self, actual: asyncio.Queue, expected: list, items_left: bool):
        await asyncio.sleep(0.001)
        for expected_msg in expected:
            actual_msg = actual.get_nowait()
            assert actual_msg == expected_msg
        assert items_left or actual.empty()

    async def verify_events(self, expected: list=None, items_left=False):
        if expected is None:
            expected = expected_events()
        await self._verify(self.events, expected, items_left)

    async def verify_data(self, expected: list=None, items_left=False):
        if expected is None:
            expected = expected_data()
        await self._verify(self.data, expected, items_left)

    async def verify(self, expected_events: list=None, expected_data: list=None, items_left=False):
        await self.verify_events(expected_events, items_left)
        await self.verify_data(expected_data, items_left)


@pytest.fixture
def serial_data():
    chunks = [
        '<add>0A<id>00<OneWir<!connected:sen',
        'sor>eTem<!s',
        'paced message>pSensor>01<address>28C80E',
        '9A0300009C\n',
        '34234<!connected:mess<!interrupt>',
        'age>\n',
        '<!interrupted! ',
        'message>',
        '<invalid! event!>'
    ]

    return [c.encode() for c in chunks]


@pytest.fixture
def expected_events():
    return [
        'connected:sensor',
        'spaced message',
        'interrupt',
        'connected:message',
        'interrupted! message'
    ]


@pytest.fixture
def expected_data():
    return [
        '0A''00''01''28C80E9A0300009C',
        '34234'
    ]


@pytest.fixture
def serial_mock(mocker):
    return mocker.patch(TESTED + '.serial.serial_for_url').return_value


@pytest.fixture
def transport_mock(mocker):
    m = mocker.patch(TESTED + '.SerialTransport').return_value
    m.is_closing.return_value = False
    return m


@pytest.fixture
def tcp_create_connection_mock(app, mocker):
    app['config']['device_host'] = 'enterprise'

    tcp_transport_mock = Mock()
    tcp_transport_mock.is_closing.return_value = False

    def connect(factory, address, port):
        """Mocks behavior of loop.create_connection()"""
        protocol = factory()
        protocol.connection_made(tcp_transport_mock)
        return tcp_transport_mock, protocol

    create_connection_mock = mocker.patch.object(
        app.loop, 'create_connection',
        CoroutineMock(side_effect=connect)
    )
    return create_connection_mock


@pytest.fixture
def bound_collector(loop):
    return Collector(loop)


@pytest.fixture
def app(app, serial_mock, transport_mock):
    app['config']['device_host'] = None
    status.setup(app)
    scheduler.setup(app)
    communication.setup(app)
    return app


@pytest.fixture
async def bound_conduit(app, client, bound_collector):
    conduit = communication.get_conduit(app)
    conduit.event_callbacks.add(bound_collector.async_on_event)
    conduit.data_callbacks.add(bound_collector.async_on_data)

    return conduit


@pytest.fixture
def comports_mock(mocker):
    m = mocker.patch(TESTED + '.list_ports.comports')
    m.return_value = [
        DummyPortInfo('/dev/dummy', 'Dummy', 'USB VID:PID=1a02:b123', '1234'),
        DummyPortInfo('/dev/ttyX', 'Electron', 'USB VID:PID=2d04:c00a', '4321'),
    ]
    return m


@pytest.fixture
def grep_ports_mock(mocker):
    m = mocker.patch(TESTED + '.list_ports.grep')
    m.return_value = [
        DummyPortInfo('/dev/ttyX', 'Electron', 'USB VID:PID=2d04:c00a', '1234'),
        DummyPortInfo('/dev/ttyX', 'Electron', 'USB VID:PID=2d04:c00a', '4321'),
    ]
    return m


def _send_chunks(protocol, data=None):
    """Helper function for calling data_received() on the protocol"""
    if data is None:
        data = serial_data()

    [protocol.data_received(chunk) for chunk in data]


async def test_protocol_funcs(loop):
    transport_mock = Mock()
    coll = Collector(loop)
    p = communication.SparkProtocol(coll.on_event, coll.on_data)

    p.connection_made(transport_mock)
    p.connection_lost('exception')


async def test_coerce_messages(loop):
    coll = Collector(loop)
    p = communication.SparkProtocol(coll.on_event, coll.on_data)

    _send_chunks(p)
    await coll.verify()


async def test_coerce_partial(loop, serial_data):
    coll = Collector(loop)
    p = communication.SparkProtocol(coll.on_event, coll.on_data)

    p.data_received(serial_data[0])
    await coll.verify([], [])

    p.data_received(serial_data[1])
    await coll.verify(['connected:sensor'], [])

    p.data_received(serial_data[2])
    p.data_received(serial_data[3])
    await coll.verify(['spaced message'], ['0A''00''01''28C80E9A0300009C'])


async def test_unbound_conduit(app, client, serial_mock, transport_mock):
    conduit = communication.SparkConduit(app)

    # test pre-bind behavior
    assert not conduit.connected
    with pytest.raises(exceptions.NotConnected):
        await conduit.write('stuff')


async def test_conduit_callbacks(bound_collector, bound_conduit):
    _send_chunks(bound_conduit._protocol)
    await bound_collector.verify()


async def test_conduit_write(bound_collector, bound_conduit, transport_mock):
    # write should be ok
    await bound_conduit.write('stuff')
    transport_mock.write.assert_called_once_with(b'stuff\n')


async def test_conduit_callback_multiple(loop, bound_collector, bound_conduit):
    # Change callback handler
    coll2 = Collector(loop)
    bound_conduit.event_callbacks.add(coll2.async_on_event)
    bound_conduit.data_callbacks.add(coll2.async_on_data)

    # Coll2 should receive all callbacks now
    _send_chunks(bound_conduit._protocol)
    await bound_collector.verify()
    await coll2.verify()


async def test_conduit_remove_callbacks(bound_collector, bound_conduit):
    # Safe to call repeatedly
    bound_conduit.event_callbacks.discard(bound_collector.async_on_event)
    bound_conduit.event_callbacks.discard(bound_collector.async_on_event)

    # Should not raise any errors
    # No events received, but still getting data
    _send_chunks(bound_conduit._protocol)
    await bound_collector.verify_events([])
    await bound_collector.verify_data()

    bound_conduit.data_callbacks.discard(bound_collector.async_on_data)
    bound_conduit.data_callbacks.discard(bound_collector.async_on_data)

    # Now also not getting data
    _send_chunks(bound_conduit._protocol)
    await bound_collector.verify_events([])
    await bound_collector.verify_data([])


async def test_conduit_err_callback(bound_conduit, expected_events):
    error_cb = CoroutineMock(side_effect=RuntimeError('boom!'))
    bound_conduit.event_callbacks.add(error_cb)

    # no errors should be thrown
    _send_chunks(bound_conduit._protocol)
    await asyncio.sleep(0.01)
    assert error_cb.call_args_list == [call(bound_conduit, e) for e in expected_events]


async def test_all_ports(comports_mock):
    assert communication.all_ports()[1][0] == '/dev/ttyX'


async def test_recognized_ports(grep_ports_mock):
    dummy = grep_ports_mock()
    recognized = [r for r in communication.recognized_ports()]
    assert recognized == dummy


async def test_detect_device(grep_ports_mock):
    dummy = grep_ports_mock()
    assert communication.detect_device('dave') == 'dave'
    assert communication.detect_device() == dummy[0].device
    assert communication.detect_device(serial_number='4321') == dummy[1].device

    grep_ports_mock.return_value = [dummy[0]]
    with pytest.raises(exceptions.ConnectionImpossible):
        communication.detect_device(serial_number='4321')


async def test_tcp_connection(app, client, mocker, tcp_create_connection_mock):
    spock = communication.SparkConduit(app)

    await spock.startup(app)
    await asyncio.sleep(0.01)

    assert spock.connected
    assert tcp_create_connection_mock.call_count == 1


async def test_connect_error(app, client, mocker, tcp_create_connection_mock):
    mocker.patch(TESTED + '.RETRY_INTERVAL_S', 0.001)
    tcp_create_connection_mock.side_effect = ConnectionRefusedError

    spock = communication.SparkConduit(app)
    await spock.startup(app)

    await asyncio.sleep(0.01)
    assert not spock.connected
    await spock.shutdown(app)

    assert tcp_create_connection_mock.call_count > 1


async def test_reconnect(app, client, mocker, tcp_create_connection_mock):
    mocker.patch(TESTED + '.RETRY_INTERVAL_S', 0.001)

    spock = communication.SparkConduit(app)
    await spock.startup(app)

    await asyncio.sleep(0.01)
    assert tcp_create_connection_mock.call_count == 1

    spock._protocol.connection_lost(ConnectionError('boo!'))
    await asyncio.sleep(0.01)
    assert tcp_create_connection_mock.call_count == 2

    spock._protocol.connection_lost(None)
    await asyncio.sleep(0.01)
    assert tcp_create_connection_mock.call_count == 3
