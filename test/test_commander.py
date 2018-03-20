"""
Tests brewblox_devcon_spark.commander
"""

import pytest
from brewblox_devcon_spark import commander
from asynctest import CoroutineMock
import asyncio

TESTED = commander.__name__


@pytest.fixture
def conduit_mock(mocker):
    m = mocker.patch(TESTED + '.communication.SparkConduit')
    m.return_value.write = CoroutineMock()
    m.return_value.write_encoded = CoroutineMock()
    return m.return_value


@pytest.fixture
async def sparky(conduit_mock, loop):
    return commander.SparkCommander(loop)


async def test_init(conduit_mock, sparky, loop):
    sparky.bind(loop=loop)
    assert conduit_mock.bind.call_count == 1

    sparky.close()
    assert conduit_mock.close.call_count == 1


async def test_write(conduit_mock, sparky):
    await sparky.write('stuff')
    conduit_mock.write.assert_called_once_with('stuff')


async def test_on_data(conduit_mock, sparky):
    assert len(sparky._requests) == 0

    await sparky._on_data(conduit_mock, '05 00 00 00 00')
    await asyncio.sleep(0.0001)
    assert len(sparky._requests) == 1
    assert sparky._requests[b'\x05\x00'].qsize() == 1


async def test_on_data_error(mocker, conduit_mock, sparky):
    logger_mock = mocker.spy(commander, 'LOGGER')
    await sparky._on_data(conduit_mock, 'pancakes')

    assert len(sparky._requests) == 0
    assert logger_mock.error.call_count == 1


async def test_command(conduit_mock, sparky):
    await sparky._on_data(conduit_mock, '05 00 00 00 00')

    resp = await sparky.do('list_objects', profile_id=0)
    assert resp.opcode == 5
    assert resp.objects is None

    conduit_mock.write_encoded.assert_called_once_with(b'0500')
