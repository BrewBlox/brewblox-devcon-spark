"""
Tests brewblox_devcon_spark.commander
"""

import asyncio

import pytest
from brewblox_service import scheduler
from brewblox_service.testing import matching
from mock import AsyncMock

from brewblox_devcon_spark import (commander, commands, exceptions,
                                   service_status)

TESTED = commander.__name__


@pytest.fixture
def reset_msgid():
    commands.Command._msgid = 0


@pytest.fixture
def m_conn(mocker):
    m = mocker.patch(TESTED + '.connection.fget')
    m.return_value.bind = AsyncMock()
    m.return_value.write = AsyncMock()
    m.return_value.shutdown = AsyncMock()
    m.return_value.start_update = AsyncMock()
    m.return_value.start_reconnect = AsyncMock()
    return m.return_value


@pytest.fixture
def app(app, m_conn, mocker):
    app['config']['command_timeout'] = 1
    service_status.setup(app)
    scheduler.setup(app)
    commander.setup(app)
    return app


@pytest.fixture
async def sparky(app, client, mocker):
    s = commander.fget(app)

    # Allow immediately responding to requests
    # This avoids having to schedule parallel calls to execute() and data_callback()
    s.__preloaded = []
    f_orig = s.add_request

    def m_add_request(request: str):
        fut = f_orig(request)
        for msg in s.__preloaded:
            s.data_callback(msg)
        s.__preloaded.clear()
        return fut

    mocker.patch.object(s, 'add_request', m_add_request)
    return s


def create_future() -> asyncio.Future:
    return asyncio.get_event_loop().create_future()


async def test_init(m_conn, app, client):
    spock = commander.SparkCommander(app)

    await spock.shutdown(app)
    await spock.startup(app)
    await spock.shutdown(app)
    await spock.shutdown(app)

    assert str(spock)


async def test_on_data(sparky):
    assert len(sparky._requests) == 0

    fut = create_future()
    sparky._requests['0500'] = fut
    sparky.data_callback('05 00 |00 00 00 00')
    assert sparky._requests == {'0500': fut}
    assert fut.done()
    assert await fut == '00000000'


async def test_on_data_error(mocker, sparky):
    m_logger = mocker.spy(commander, 'LOGGER')

    # No response pipe
    sparky.data_callback('1234')
    assert len(sparky._requests) == 0
    m_logger.error.assert_called_with(matching(r'.*not enough values to unpack'))

    # Valid hex, but not expected
    sparky.data_callback('BB|AA')
    assert len(sparky._requests) == 0
    m_logger.error.assert_called_with(matching(r'.*Unexpected message'))


async def test_execute(sparky, reset_msgid, m_conn):
    sparky.__preloaded.append('01 00 07 28 | 00 00 00')

    cmd = commands.ListStoredObjectsCommand.from_args()
    resp = await sparky.execute(cmd)
    assert resp['objects'] == []

    m_conn.write.assert_called_once_with('01000728')


async def test_error_command(sparky, reset_msgid):
    sparky.__preloaded.append('01 00 07 28 | FF 00')
    command = commands.ListStoredObjectsCommand.from_args()

    with pytest.raises(exceptions.CommandException):
        await sparky.execute(command)


async def test_timeout_command(sparky, mocker):
    mocker.patch.object(sparky, '_timeout', 0.001)
    with pytest.raises(exceptions.CommandTimeout):
        await sparky.execute(commands.ListStoredObjectsCommand.from_args())


async def test_start_reconnect(app, sparky, m_conn):
    await sparky.start_reconnect()
    m_conn.start_reconnect.assert_awaited_once()
    await sparky.shutdown(app)
    await sparky.start_reconnect()
    m_conn.start_reconnect.assert_awaited_once()
