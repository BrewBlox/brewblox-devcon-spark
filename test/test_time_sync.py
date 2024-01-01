"""
Tests brewblox_devcon_spark.time_sync
"""

import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import timedelta
from unittest.mock import Mock

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from pytest_mock import MockerFixture

from brewblox_devcon_spark import (codec, command, connection, control,
                                   datastore, mqtt, state_machine,
                                   synchronization, time_sync, utils)

TESTED = time_sync.__name__


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(mqtt.lifespan())
        await stack.enter_async_context(connection.lifespan())
        await stack.enter_async_context(synchronization.lifespan())
        await state_machine.CV.get().wait_synchronized()
        yield


@pytest.fixture
def app() -> FastAPI():
    config = utils.get_config()
    config.mock = True
    config.time_sync_interval = timedelta(milliseconds=1)
    config.time_sync_retry_interval = timedelta(milliseconds=1)

    mqtt.setup()
    state_machine.setup()
    datastore.setup()
    codec.setup()
    connection.setup()
    command.setup()
    control.setup()
    return FastAPI(lifespan=lifespan)


@pytest.fixture(autouse=True)
async def manager(manager: LifespanManager):
    yield manager


@pytest.fixture
def s_patch_block(app: FastAPI, mocker: MockerFixture) -> Mock:
    s = mocker.spy(control.CV.get(), 'patch_block')
    return s


async def test_sync(s_patch_block: Mock):
    config = utils.get_config()
    sync = time_sync.TimeSync()
    await sync.run()
    assert s_patch_block.call_count == 1

    # Normal repeat
    s_patch_block.reset_mock()
    async with time_sync.lifespan():
        await asyncio.sleep(0.1)
        assert s_patch_block.call_count >= 1

        s_patch_block.reset_mock()
        s_patch_block.side_effect = RuntimeError
        await asyncio.sleep(0.1)
        assert s_patch_block.call_count >= 1

    # Disabled repeat
    config.time_sync_interval = timedelta(seconds=-1)
    await asyncio.wait_for(sync.repeat(), timeout=1)
