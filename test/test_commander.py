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
    m = mocker.patch(TESTED + '.communication.get_conduit')
    m.return_value.bind = CoroutineMock()
    m.return_value.write = CoroutineMock()
    m.return_value.write_encoded = CoroutineMock()
    return m.return_value


@pytest.fixture
def app(app, conduit_mock):
    commander.setup(app)
    return app


@pytest.fixture
async def sparky(app, client):
    return commander.get_commander(app)


async def test_init(conduit_mock, app, client):
    spock = commander.SparkCommander()

    await spock.shutdown()
    await spock.startup(app)
    await spock.shutdown()
    await spock.shutdown()

    assert str(spock)


async def test_process_response(conduit_mock, sparky):
    assert len(sparky._requests) == 0

    await sparky._process_response(conduit_mock, '05 00 |00 00 00')
    await asyncio.sleep(0.0001)
    assert len(sparky._requests) == 1
    assert sparky._requests[b'\x05\x00'].queue.qsize() == 1


async def test_process_response_error(mocker, conduit_mock, sparky):
    logger_mock = mocker.spy(commander, 'LOGGER')

    # No response pipe
    await sparky._process_response(conduit_mock, '1234')
    assert len(sparky._requests) == 0
    assert logger_mock.error.call_count == 1

    # Not a hex string
    await sparky._process_response(conduit_mock, 'pancakes|tasty')

    assert len(sparky._requests) == 0
    assert logger_mock.error.call_count == 2

    # Valid hex, not an opcode
    # process_response does not validate - it will be cleaned up later
    await sparky._process_response(conduit_mock, 'BB|AA')
    assert len(sparky._requests) == 1
    assert logger_mock.error.call_count == 2


async def test_command(conduit_mock, sparky):
    await sparky._process_response(conduit_mock, '05 00 |00')

    command = commands.ListObjectsCommand().from_args(profile_id=0)
    resp = await sparky.execute(command)
    assert resp['objects'] is None

    conduit_mock.write_encoded.assert_called_once_with(b'0500')


async def test_error_command(conduit_mock, sparky):
    command = commands.ListObjectsCommand().from_args(profile_id=0)
    await sparky._process_response(conduit_mock, '05 00 |FF 00 00')

    with pytest.raises(commands.CommandException):
        await sparky.execute(command)


async def test_stale_reply(conduit_mock, sparky):
    # error code
    stale = commander.TimestampedResponse(b'\xff\x00')
    stale._timestamp -= timedelta(minutes=1)
    fresh = commander.TimestampedResponse(b'\x00\x00\x00')

    q = sparky._requests[b'\x05\x00'].queue
    await q.put(stale)
    await q.put(fresh)

    command = commands.ListObjectsCommand().from_args(profile_id=0)
    assert await sparky.execute(command)


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


async def test_queue_cleanup(mocker, conduit_mock, sparky, app):
    mocker.patch(TESTED + '.CLEANUP_INTERVAL', timedelta(milliseconds=10))
    fresh_mock = PropertyMock(return_value=True)
    type(commander.TimestampedQueue()).fresh = fresh_mock

    await sparky.startup(app)
    await sparky._process_response(conduit_mock, '05 00 |00 00 00')

    # Still fresh
    await asyncio.sleep(0.1)
    assert len(sparky._requests) == 1

    # Assert stale was removed
    fresh_mock.return_value = False
    await asyncio.sleep(0.1)
    assert len(sparky._requests) == 0


async def test_queue_cleanup_error(mocker, sparky, app):
    mocker.patch(TESTED + '.CLEANUP_INTERVAL', timedelta(milliseconds=10))
    logger_spy = mocker.spy(commander, 'LOGGER')

    # Trigger an error
    sparky._requests = None

    await sparky.startup(app)
    await asyncio.sleep(0.1)
    assert logger_spy.warn.call_count > 0
    assert not sparky._cleanup_task.done()
