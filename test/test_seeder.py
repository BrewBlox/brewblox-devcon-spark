"""
Tests brewblox_devcon_spark.seeder
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from brewblox_devcon_spark import (commander_sim, datastore, device, seeder,
                                   state)
from brewblox_devcon_spark.codec import codec
from brewblox_service import brewblox_logger, scheduler

TESTED = seeder.__name__
LOGGER = brewblox_logger(__name__)


def states(app):
    events = state.get_events(app)
    return [
        events.disconnect_ev.is_set(),
        events.connect_ev.is_set(),
        events.synchronize_ev.is_set(),
    ]


async def connect(app):
    await state.on_connect(app, 'seeder test')
    await seeder.get_seeder(app).seeding_done()
    await asyncio.sleep(0.01)


async def disconnect(app):
    await state.on_disconnect(app)
    await state.wait_disconnect(app)
    await asyncio.sleep(0.01)


@pytest.fixture(autouse=True)
async def ping_interval_mock(mocker):
    mocker.patch(TESTED + '.PING_INTERVAL_S', 0.0001)


@pytest.fixture(autouse=True)
async def system_exit_mock(mocker):
    m = mocker.patch(TESTED + '.SystemExit')
    return m


@pytest.fixture
async def app(app):
    state.setup(app)
    scheduler.setup(app)
    datastore.setup(app)
    commander_sim.setup(app)
    codec.setup(app)
    device.setup(app)
    seeder.setup(app)
    return app


@pytest.fixture
def store(app):
    return datastore.get_datastore(app)


@pytest.fixture
def api_mock(mocker):
    m = mocker.patch(TESTED + '.object_api.ObjectApi').return_value
    m.read = AsyncMock()
    m.write = AsyncMock()
    return m


@pytest.fixture
def config(app):
    return datastore.get_config(app)


async def test_seed_status(app, client, mocker):
    await state.wait_synchronize(app)
    assert states(app) == [False, True, True]

    await disconnect(app)
    assert states(app) == [True, False, False]

    await connect(app)
    assert states(app) == [False, True, True]


async def test_seed_errors(app, client, mocker, system_exit_mock):
    await state.wait_synchronize(app)
    mocker.patch(TESTED + '.datastore.check_remote', AsyncMock(side_effect=RuntimeError))

    await disconnect(app)
    await connect(app)

    assert states(app) == [False, True, False]
    assert system_exit_mock.call_count == 1
    assert not seeder.get_seeder(app).active


async def test_write_error(app, client, mocker, api_mock, system_exit_mock):
    await state.wait_synchronize(app)
    api_mock.write = AsyncMock(side_effect=RuntimeError)
    await disconnect(app)
    await connect(app)

    assert states(app) == [False, True, False]
    assert system_exit_mock.call_count == 1
    assert not seeder.get_seeder(app).active


async def test_timeout(app, client, mocker, api_mock, system_exit_mock):
    await state.wait_synchronize(app)
    await disconnect(app)
    mocker.patch(TESTED + '.HANDSHAKE_TIMEOUT_S', 0.0001)
    s = seeder.get_seeder(app)
    mocker.patch.object(s, '_ping_controller', AsyncMock())

    await connect(app)
    assert system_exit_mock.call_count == 1
    assert not seeder.get_seeder(app).active
