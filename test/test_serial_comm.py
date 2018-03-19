"""
Tests brewblox_devcon_spark.serial_comm
"""

import asyncio
import logging
from unittest.mock import Mock, call

import pytest
from asynctest import CoroutineMock

from brewblox_devcon_spark import serial_comm

TESTED = serial_comm.__name__
LOGGER = logging.getLogger(__name__)


class Collector():
    def __init__(self, loop):
        self.events = asyncio.Queue(loop=loop)
        self.data = asyncio.Queue(loop=loop)

    def on_event(self, e):
        self.events.put_nowait(e)

    def on_data(self, d):
        self.data.put_nowait(d)

    async def async_on_event(self, conduit, e):
        await self.events.put_nowait(e)

    async def async_on_data(self, conduit, d):
        await self.data.put_nowait(d)

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
        '<add>0A<id>00<OneWir<!connected:sen'.encode(),
        'sor>eTem<!s'.encode(),
        'paced message>pSensor>01<address>28C80E'.encode(),
        '9A0300009C\n'.encode(),
        '34234<!connected:mess<!interrupt>'.encode(),
        'age>\n'.encode(),
        '<!interrupted '.encode(),
        'message>'.encode()
    ]

    return chunks


@pytest.fixture
def expected_events():
    return [
        'connected:sensor',
        'spaced message',
        'interrupt',
        'connected:message',
        'interrupted message'
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
    return mocker.patch(TESTED + '.SerialTransport').return_value


@pytest.fixture
def bound_collector(loop):
    return Collector(loop)


@pytest.fixture
def bound_conduit(loop, serial_mock, transport_mock, bound_collector):
    conduit = serial_comm.SparkConduit(
        on_event=bound_collector.async_on_event,
        on_data=bound_collector.async_on_data)
    conduit.bind('port', loop)

    return conduit


@pytest.fixture
def list_ports_mock(mocker):
    m = mocker.patch(TESTED + '.list_ports.comports')
    m.return_value = [('/dev/ttyX', 'Electron', 'USB VID:PID=2d04:c00a')]
    return m


def _send_chunks(protocol, data=None):
    """Helper function for calling data_received() on the protocol"""
    if data is None:
        data = serial_data()

    [protocol.data_received(chunk) for chunk in data]


async def test_protocol_funcs(loop):
    transport_mock = Mock()
    coll = Collector(loop)
    p = serial_comm.SparkProtocol(coll.on_event, coll.on_data)

    p.connection_made(transport_mock)
    assert transport_mock.serial.rts is False

    p.connection_lost('exception')


async def test_coerce_messages(loop):
    coll = Collector(loop)
    p = serial_comm.SparkProtocol(coll.on_event, coll.on_data)

    _send_chunks(p)
    await coll.verify()


async def test_coerce_partial(loop, serial_data):
    coll = Collector(loop)
    p = serial_comm.SparkProtocol(coll.on_event, coll.on_data)

    p.data_received(serial_data[0])
    await coll.verify([], [])

    p.data_received(serial_data[1])
    await coll.verify(['connected:sensor'], [])

    p.data_received(serial_data[2])
    p.data_received(serial_data[3])
    await coll.verify(['spaced message'], ['0A''00''01''28C80E9A0300009C'])


async def test_unbound_conduit(loop, serial_mock, transport_mock):
    coll = Collector(loop)
    conduit = serial_comm.SparkConduit(
        on_event=coll.async_on_event,
        on_data=coll.async_on_data)

    # test pre-bind behavior
    assert not conduit.is_bound
    with pytest.raises(AssertionError):
        await conduit.write('stuff')


async def test_conduit_callbacks(bound_collector, bound_conduit):
    # bind, and test callbacks provided in init
    _send_chunks(bound_conduit._protocol)
    await bound_collector.verify()


async def test_conduit_write(bound_collector, bound_conduit, serial_mock):
    # write should be ok
    await bound_conduit.write('stuff')
    serial_mock.write.assert_called_once_with('stuff')


async def test_conduit_callback_change(loop, bound_collector, bound_conduit):
    # Change callback handler
    coll2 = Collector(loop)
    bound_conduit.on_event = coll2.async_on_event
    bound_conduit.on_data = coll2.async_on_data

    # Coll2 should receive all callbacks now
    _send_chunks(bound_conduit._protocol)
    await bound_collector.verify([], [])
    await coll2.verify()


async def test_conduit_none_callback(bound_collector, bound_conduit):
    bound_conduit.on_event = None

    # Should not raise any errors
    _send_chunks(bound_conduit._protocol)

    # No events received, but still getting data
    await bound_collector.verify_events([])
    await bound_collector.verify_data()


async def test_conduit_err_callback(loop, serial_mock, transport_mock, expected_events):
    error_cb = CoroutineMock(side_effect=RuntimeError('boom!'))
    conduit = serial_comm.SparkConduit(
        on_event=error_cb,
        on_data=None
    )
    conduit.bind('port', loop)

    # no errors should be thrown
    _send_chunks(conduit._protocol)
    assert error_cb.call_args_list == [call(conduit, e) for e in expected_events]
