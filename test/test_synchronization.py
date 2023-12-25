"""
Tests brewblox_devcon_spark.synchronization
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from pytest_mock import MockerFixture

from brewblox_devcon_spark import (codec, commander, connection, const,
                                   datastore, exceptions, mqtt, state_machine,
                                   synchronization, utils)
from brewblox_devcon_spark.datastore import block_store, settings_store
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
    store = settings_store.CV.get()
    sync = synchronization.SparkSynchronization()

    store.service_settings.enabled = True
    await sync.synchronize()


async def disconnect():
    store = settings_store.CV.get()
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
def app(mocker: MockerFixture) -> FastAPI:
    mocker.patch(connection.connection_handler.__name__ + '.BASE_RECONNECT_DELAY', timedelta())
    mocker.patch(connection.connection_handler.__name__ + '.MAX_RECONNECT_DELAY', timedelta())

    state_machine.setup()
    mqtt.setup()
    codec.setup()
    datastore.setup()
    connection.setup()
    commander.setup()

    return FastAPI(lifespan=lifespan)


@pytest.fixture
def m_load_blocks(app: FastAPI, mocker: MockerFixture):
    m = mocker.patch.object(block_store.CV.get(), 'load', autospec=True)
    return m


@pytest.fixture(autouse=True)
async def client(client: AsyncClient, m_load_blocks: AsyncMock):
    yield client


async def test_sync_status(m_sleep):
    await connect()
    assert states() == [False, True, True, True]

    await disconnect()
    assert states() == [True, False, False, False]

    await connect()
    assert states() == [False, True, True, True]


async def test_sync_errors(m_load_blocks: AsyncMock):
    m_load_blocks.side_effect = RuntimeError

    with pytest.raises(RuntimeError):
        await connect()

    assert states() == [False, True, True, False]


async def test_write_error(mocker: MockerFixture):
    m_patch_block = mocker.patch.object(commander.CV.get(), 'patch_block', autospec=True)
    m_patch_block.return_value = FirmwareBlock(
        nid=const.SYSINFO_NID,
        type='ErrorObject',
        data={'error': 'something went wrong'}
    )

    with pytest.raises(exceptions.CommandException):
        await connect()

    assert states() == [False, True, True, False]


async def test_handshake_timeout(mocker: MockerFixture):
    mocker.patch(TESTED + '.HANDSHAKE_TIMEOUT', timedelta(milliseconds=100))
    m_version = mocker.patch.object(commander.CV.get(), 'version', autospec=True)
    m_version.side_effect = RuntimeError

    with pytest.raises(asyncio.TimeoutError):
        await connect()


async def test_device_name():
    config = utils.get_config()
    s = synchronization.SparkSynchronization()

    config.mock = True
    config.simulation = False
    await connect()
    assert s.device_name == config.device_id
    await disconnect()

    config.mock = False
    config.simulation = True
    await connect()
    assert s.device_name == f'simulator__{config.name}'


async def test_on_global_store_change():
    store = settings_store.CV.get()
    sync = synchronization.SparkSynchronization()

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
        s = synchronization.SparkSynchronization()
        await asyncio.wait_for(s.run(), timeout=0.2)


async def test_invalid_error(mocker: MockerFixture):
    state = state_machine.CV.get()
    state._status_desc.service.device.device_id = 'XXX'

    with pytest.raises(exceptions.InvalidDeviceId):
        await connect()
    assert states() == [False, True, True, False]

    # run() catches InvalidDeviceId
    with pytest.raises(asyncio.TimeoutError):
        s = synchronization.SparkSynchronization()
        await asyncio.wait_for(s.run(), timeout=0.2)
