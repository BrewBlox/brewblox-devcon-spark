"""
Tests brewblox_devcon_spark.broadcast
"""

import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import timedelta
from unittest.mock import ANY, Mock, call

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from pytest_mock import MockerFixture

from brewblox_devcon_spark import (broadcast, codec, command, connection,
                                   control, datastore_blocks,
                                   datastore_settings, exceptions, mqtt,
                                   state_machine, synchronization, utils)
from brewblox_devcon_spark.connection import mock_connection
from brewblox_devcon_spark.models import ErrorCode

TESTED = broadcast.__name__


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(mqtt.lifespan())
        await stack.enter_async_context(connection.lifespan())
        await stack.enter_async_context(synchronization.lifespan())
        yield


@pytest.fixture
def app() -> FastAPI():
    config = utils.get_config()
    config.mock = True
    config.broadcast_interval = timedelta(milliseconds=1)

    mqtt.setup()
    state_machine.setup()
    datastore_settings.setup()
    datastore_blocks.setup()
    codec.setup()
    connection.setup()
    command.setup()
    control.setup()
    return FastAPI(lifespan=lifespan)


@pytest.fixture(autouse=True)
async def manager(manager: LifespanManager):
    yield manager


@pytest.fixture(autouse=True)
async def synchronized(manager: LifespanManager):
    await state_machine.CV.get().wait_synchronized()


@pytest.fixture
def s_publish(mocker: MockerFixture):
    mqtt_client = mqtt.CV.get()
    m = mocker.spy(mqtt_client, 'publish')
    return m


async def test_broadcast_unsync(s_publish: Mock):
    state = state_machine.CV.get()
    state._synchronized_ev.clear()

    b = broadcast.Broadcaster()
    await b.run()
    assert s_publish.call_count == 1


async def test_broadcast(s_publish: Mock):
    config = utils.get_config()
    b = broadcast.Broadcaster()
    await b.run()

    s_publish.assert_has_calls([
        call('brewcast/history/sparkey', ANY),
        call('brewcast/state/sparkey', ANY, retain=True),
    ])
    s_publish.reset_mock()

    async with broadcast.lifespan():
        mock_connection.NEXT_ERROR.append(ErrorCode.UNKNOWN_ERROR)
        await asyncio.sleep(0.2)
        assert s_publish.call_count > 1

    # Early exit if interval <= 0
    s_publish.reset_mock()
    config.broadcast_interval = timedelta()
    async with utils.task_context(b.repeat()) as task:
        await asyncio.sleep(0.1)
        assert task.done()
        assert s_publish.call_count == 0


async def test_error(s_publish: Mock):
    b = broadcast.Broadcaster()
    mock_connection.NEXT_ERROR.append(ErrorCode.UNKNOWN_ERROR)
    with pytest.raises(exceptions.CommandException):
        await b.run()

    # Error over, resume normal work
    # 1 * only state event
    # 1 * history + state
    await b.run()
    assert s_publish.call_count == 3


async def test_api_broadcaster(s_publish: Mock):
    b = broadcast.Broadcaster()
    await b.run()
    assert s_publish.call_count == 2
