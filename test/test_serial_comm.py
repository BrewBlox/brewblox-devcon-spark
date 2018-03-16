"""
Tests brewblox_devcon_spark.serial_comm
"""

import asyncio
import logging
from unittest.mock import Mock

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
def list_ports_mock(mocker):
    m = mocker.patch(TESTED + '.list_ports.comports')
    m.return_value = [('/dev/ttyX', 'Electron', 'USB VID:PID=2d04:c00a')]
    return m


async def test_protocol_funcs(loop):
    transport_mock = Mock()
    coll = Collector(loop)
    p = serial_comm.SparkProtocol(coll.on_event, coll.on_data)

    p.connection_made(transport_mock)
    assert transport_mock.serial.rts is False

    p.connection_lost('exception')


async def test_coerce_messages(loop, serial_data, expected_events, expected_data):
    coll = Collector(loop)
    p = serial_comm.SparkProtocol(coll.on_event, coll.on_data)
    [p.data_received(chunk) for chunk in serial_data]

    assert len(expected_events) == coll.events.qsize()
    for expected in expected_events:
        actual = coll.events.get_nowait()
        assert actual == expected

    assert len(expected_data) == coll.data.qsize()
    for expected in expected_data:
        actual = coll.data.get_nowait()
        assert actual == expected


async def test_coerce_partial(loop, serial_data):
    coll = Collector(loop)
    p = serial_comm.SparkProtocol(coll.on_event, coll.on_data)

    p.data_received(serial_data[0])
    assert coll.events.empty()
    assert coll.data.empty()

    p.data_received(serial_data[1])
    assert coll.events.get_nowait() == 'connected:sensor'
    assert coll.data.empty()

    p.data_received(serial_data[2])
    p.data_received(serial_data[3])
    assert coll.events.get_nowait() == 'spaced message'
    assert coll.data.get_nowait() == '0A''00''01''28C80E9A0300009C'

    assert coll.events.empty()
    assert coll.data.empty()


async def test_conduit(mocker, loop, serial_data, expected_events, expected_data):
    serial_mock = mocker.patch(TESTED + '.serial.serial_for_url').return_value
    mocker.patch(TESTED + '.SerialTransport')

    async def test_callbacks(c: Collector):
        [conduit._protocol.data_received(chunk) for chunk in serial_data]
        # Allow event loop to process async calls inside the sync data_received() func
        await asyncio.sleep(0.001)

        for expected in expected_events:
            actual = c.events.get_nowait()
            assert actual == expected
        assert c.events.empty()

        for expected in expected_data:
            actual = c.data.get_nowait()
            assert actual == expected
        assert c.events.empty()

    coll = Collector(loop)
    conduit = serial_comm.SparkConduit(
        on_event=coll.async_on_event,
        on_data=coll.async_on_data)

    # test pre-bind behavior
    assert not conduit.is_bound
    with pytest.raises(AssertionError):
        await conduit.write('stuff')

    # bind, and test callbacks provided in init
    conduit.bind('port', loop)
    await test_callbacks(coll)

    # write should be ok
    await conduit.write('stuff')
    serial_mock.write.assert_called_once_with('stuff')

    # Change callback handler
    coll2 = Collector(loop)
    conduit.on_event = coll2.async_on_event
    conduit.on_data = coll2.async_on_data
    await test_callbacks(coll2)

    # None callback shouldn't break it
    conduit.on_event = None
    conduit.on_data = None
    [conduit._protocol.data_received(chunk) for chunk in serial_data]

    # Error in callback shouldn't break it
    error_cb = CoroutineMock(side_effect=RuntimeError)
    conduit.on_event = error_cb
    [conduit._protocol.data_received(chunk) for chunk in serial_data]
    assert error_cb.call_count == len(expected_events)
