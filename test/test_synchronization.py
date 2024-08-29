import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from pytest_mock import MockerFixture

from brewblox_devcon_spark import (codec, command, connection, const,
                                   datastore_blocks, datastore_settings,
                                   exceptions, mqtt, state_machine,
                                   synchronization, utils)
from brewblox_devcon_spark.models import FirmwareBlock

TESTED = synchronization.__name__


def states():
    state = state_machine.CV.get()
    return [
        state.is_disconnected(),
        state.is_connected(),
        state.is_acknowledged(),
        state.is_synchronized(),
    ]


async def connect():
    store = datastore_settings.CV.get()
    sync = synchronization.StateSynchronizer()

    store.service_settings.enabled = True
    await sync.synchronize()


async def disconnect():
    store = datastore_settings.CV.get()
    state = state_machine.CV.get()
    conn = connection.CV.get()

    store.service_settings.enabled = False
    state.set_enabled(False)
    await conn.reset()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with connection.lifespan():
        yield


@pytest.fixture
def app() -> FastAPI:
    state_machine.setup()
    mqtt.setup()
    codec.setup()
    datastore_settings.setup()
    datastore_blocks.setup()
    connection.setup()
    command.setup()

    return FastAPI(lifespan=lifespan)


@pytest.fixture(autouse=True)
async def manager(manager: LifespanManager):
    yield manager


async def test_sync_status(m_sleep):
    await connect()
    assert states() == [False, True, True, True]

    await disconnect()
    assert states() == [True, False, False, False]

    await connect()
    assert states() == [False, True, True, True]


async def test_sync_errors(mocker: MockerFixture):
    m_read_names = mocker.patch.object(command.CV.get(), 'read_all_block_names', autospec=True)
    m_read_names.side_effect = RuntimeError

    with pytest.raises(RuntimeError):
        await connect()

    assert states() == [False, True, True, False]


async def test_write_error(mocker: MockerFixture):
    m_patch_block = mocker.patch.object(command.CV.get(), 'patch_block', autospec=True)
    m_patch_block.return_value = FirmwareBlock(
        nid=const.SYSINFO_NID,
        type='ErrorObject',
        data={'error': 'something went wrong'}
    )

    s = synchronization.StateSynchronizer()

    with pytest.raises(exceptions.CommandException):
        await s.synchronize()

    # synchronize raises error after acknowledge
    assert states() == [False, True, True, False]

    # run catches error
    await s.run()

    # state is reset to disconnected
    assert states() == [True, False, False, False]


async def test_handshake_timeout(mocker: MockerFixture):
    config = utils.get_config()
    config.handshake_timeout = timedelta(milliseconds=100)
    m_version = mocker.patch.object(command.CV.get(), 'version', autospec=True)
    m_version.side_effect = RuntimeError

    with pytest.raises(asyncio.TimeoutError):
        await connect()


async def test_on_global_store_change():
    store = datastore_settings.CV.get()
    sync = synchronization.StateSynchronizer()

    # Update during runtime
    await connect()
    store.unit_settings.temperature = 'degF'
    store.timezone_settings.name = 'Africa/Casablanca'
    await sync._apply_global_settings()

    # Should safely handle disconnected state
    await disconnect()
    await sync._apply_global_settings()


async def test_incompatible_error(mocker: MockerFixture):
    state = state_machine.CV.get()
    state._status_desc.service.firmware.proto_version = 'ABCD'

    with pytest.raises(exceptions.IncompatibleFirmware):
        await connect()
    assert states() == [False, True, True, False]

    # run() catches IncompatibleFirmware
    with pytest.raises(asyncio.TimeoutError):
        s = synchronization.StateSynchronizer()
        await asyncio.wait_for(s.run(), timeout=0.2)


async def test_invalid_error(mocker: MockerFixture):
    state = state_machine.CV.get()
    state._status_desc.service.device.device_id = 'XXX'

    with pytest.raises(exceptions.InvalidDeviceId):
        await connect()
    assert states() == [False, True, True, False]

    # run() catches InvalidDeviceId
    with pytest.raises(asyncio.TimeoutError):
        s = synchronization.StateSynchronizer()
        await asyncio.wait_for(s.run(), timeout=0.2)
