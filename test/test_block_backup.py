"""
Tests brewblox_devcon_spark.backup
"""

import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import timedelta

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from pytest_mock import MockerFixture

from brewblox_devcon_spark import (block_backup, codec, command, connection,
                                   control, datastore_blocks,
                                   datastore_settings, mqtt, state_machine,
                                   synchronization, utils)
from brewblox_devcon_spark.models import Backup, BackupIdentity

TESTED = block_backup.__name__


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
    config.backup_interval = timedelta(milliseconds=1)
    config.backup_retry_interval = timedelta(milliseconds=1)

    mqtt.setup()
    state_machine.setup()
    datastore_settings.setup()
    datastore_blocks.setup()
    codec.setup()
    connection.setup()
    command.setup()
    control.setup()
    block_backup.setup()
    return FastAPI(lifespan=lifespan)


@pytest.fixture(autouse=True)
async def manager(manager: LifespanManager):
    yield manager


@pytest.fixture(autouse=True)
async def synchronized(manager: LifespanManager):
    await state_machine.CV.get().wait_synchronized()


async def test_inactive():
    storage = block_backup.CV.get()
    config = utils.get_config()
    config.backup_interval = timedelta()
    config.backup_retry_interval = timedelta()

    # Early exit when backup_interval <= 0
    await asyncio.wait_for(storage.repeat(), timeout=1)


async def test_autosave(mocker: MockerFixture):
    state = state_machine.CV.get()
    storage = block_backup.CV.get()
    ctrl = control.CV.get()

    await storage.run()

    stored = await storage.all()
    assert len(stored) == 1
    assert isinstance(stored[0], BackupIdentity)

    data = await storage.read(stored[0])
    assert isinstance(data, Backup)

    m_make = mocker.patch.object(ctrl, 'make_backup', autospec=True)
    m_make.return_value = Backup(blocks=[], store=[])

    async with utils.task_context(storage.repeat()) as task:
        await asyncio.sleep(0.1)
        assert m_make.call_count > 0

        m_make.side_effect = RuntimeError
        m_make.reset_mock()
        await asyncio.sleep(0.01)
        assert m_make.call_count > 0
        assert not task.done()

    with pytest.raises(RuntimeError):
        await storage.run()

    # Synchronized is checked before controller call
    # run() exits before the RuntimeError is raised
    state.set_disconnected()
    await storage.run()

    # No new entries were added
    stored = await storage.all()
    assert len(stored) == 1
