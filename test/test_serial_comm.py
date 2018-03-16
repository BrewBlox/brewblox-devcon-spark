"""
Tests brewblox_devcon_spark.serial_comm
"""

import pytest
from brewblox_devcon_spark import serial_comm

TESTED = serial_comm.__name__


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


async def test_coerce_events(loop, serial_data):
    p = serial_comm.SerialProtocol(loop)
    [p.data_received(chunk) for chunk in serial_data]

    expected_items = [
        'connected:sensor',
        'spaced message',
        'interrupt',
        'connected:message',
        'interrupted message'
    ]
    assert len(expected_items) == p.events.qsize()
    for expected in expected_items:
        actual = p.events.get_nowait()
        assert actual == expected


async def test_coerce_data(loop, serial_data):
    p = serial_comm.SerialProtocol(loop)
    [p.data_received(chunk) for chunk in serial_data]

    expected_items = [
        '0A''00''01''28C80E9A0300009C',
        '34234'
    ]
    assert len(expected_items) == p.data.qsize()
    for expected in expected_items:
        actual = p.data.get_nowait()
        assert actual == expected


async def test_coerce_partial(loop, serial_data):
    p = serial_comm.SerialProtocol(loop)

    p.data_received(serial_data[0])
    assert p.events.empty()
    assert p.data.empty()

    p.data_received(serial_data[1])
    assert p.events.get_nowait() == 'connected:sensor'
    assert p.data.empty()

    p.data_received(serial_data[2])
    p.data_received(serial_data[3])
    assert p.events.get_nowait() == 'spaced message'
    assert p.data.get_nowait() == '0A''00''01''28C80E9A0300009C'

    assert p.events.empty()
    assert p.data.empty()
