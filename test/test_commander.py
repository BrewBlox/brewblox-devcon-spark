"""
Tests brewblox_devcon_spark.commander
"""

import asyncio
from datetime import timedelta
from unittest.mock import PropertyMock

import pytest
from asynctest import CoroutineMock

from brewblox_devcon_spark import commander, commands

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
    await sparky.close()
    assert conduit_mock.close.call_count == 1

    await sparky.bind(loop=loop)
    assert conduit_mock.bind.call_count == 1

    await sparky.close()
    await sparky.close()
    assert conduit_mock.close.call_count == 3

    assert str(sparky)


async def test_write(conduit_mock, sparky):
    await sparky.write('stuff')
    conduit_mock.write.assert_called_once_with('stuff')


async def test_on_data(conduit_mock, sparky):
    assert len(sparky._requests) == 0

    await sparky._on_data(conduit_mock, '05 00 |00 00 00')
    await asyncio.sleep(0.0001)
    assert len(sparky._requests) == 1
    assert sparky._requests[b'\x05\x00'].queue.qsize() == 1


async def test_on_data_error(mocker, conduit_mock, sparky):
    logger_mock = mocker.spy(commander, 'LOGGER')

    # No response pipe
    await sparky._on_data(conduit_mock, '1234')
    assert len(sparky._requests) == 0
    assert logger_mock.error.call_count == 1

    # Not a hex string
    await sparky._on_data(conduit_mock, 'pancakes|tasty')

    assert len(sparky._requests) == 0
    assert logger_mock.error.call_count == 2

    # valid hex, not an opcode
    await sparky._on_data(conduit_mock, 'BB|AA')
    assert len(sparky._requests) == 0
    assert logger_mock.error.call_count == 3


async def test_command(conduit_mock, sparky):
    await sparky._on_data(conduit_mock, '05 00 |00 00 00')

    resp = await sparky.do('list_objects', dict(profile_id=0))
    assert resp.objects is None

    conduit_mock.write_encoded.assert_called_once_with(b'0500')


async def test_error_command(conduit_mock, sparky):
    await sparky._on_data(conduit_mock, '05 00 |FF 00 00')

    with pytest.raises(commands.CommandException):
        await sparky.do('list_objects', dict(profile_id=0))


async def test_stale_reply(conduit_mock, sparky):
    stale = commander.TimestampedResponse('stale')
    stale._timestamp -= timedelta(minutes=1)
    fresh = commander.TimestampedResponse('fresh')

    q = sparky._requests[b'\x05\x00'].queue
    await q.put(stale)
    await q.put(fresh)

    resp = await sparky.do('list_objects', dict(profile_id=0))
    assert resp == 'fresh'


async def test_timestamped_queue():
    q = commander.TimestampedQueue()
    assert q.fresh

    q._timestamp -= 2*commander.QUEUE_VALID_DURATION
    assert not q.fresh

    # retrieving the queue should reset timestamp
    assert q.queue.empty()
    assert q.fresh


async def test_timestamped_response():
    res = commander.TimestampedResponse('data')
    assert res.fresh

    res._timestamp -= 2*commander.RESPONSE_VALID_DURATION
    assert not res.fresh

    # retrieving data does not reset timestamp
    assert res.content == 'data'
    assert not res.fresh


async def test_queue_cleanup(mocker, conduit_mock, sparky):
    mocker.patch(TESTED + '.CLEANUP_INTERVAL_S', 0.01)
    fresh_mock = PropertyMock(return_value=True)
    type(commander.TimestampedQueue()).fresh = fresh_mock

    await sparky.bind()
    await sparky._on_data(conduit_mock, '05 00 |00 00 00')

    # Still fresh
    await asyncio.sleep(0.1)
    assert len(sparky._requests) == 1

    # Assert stale was removed
    fresh_mock.return_value = False
    await asyncio.sleep(0.1)
    assert len(sparky._requests) == 0
