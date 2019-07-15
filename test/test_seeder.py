"""
Tests brewblox_devcon_spark.seeder
"""

import asyncio

import pytest
from asynctest import CoroutineMock
from brewblox_service import brewblox_logger, scheduler

from brewblox_devcon_spark import (commander_sim, datastore, device, seeder,
                                   status)
from brewblox_devcon_spark.codec import codec

TESTED = seeder.__name__
LOGGER = brewblox_logger(__name__)


def states(app):
    state = status.get_status(app)
    return [
        state.is_disconnected,
        state.is_connected,
        state.is_synchronized,
    ]


async def synchronized(app):
    state = status.get_status(app)
    await state.wait_synchronize()


async def connect(app):
    state = status.get_status(app)
    await state.on_connect('seeder test')
    await seeder.get_seeder(app).seeding_done()
    await asyncio.sleep(0.01)


async def disconnect(app):
    state = status.get_status(app)
    await state.on_disconnect()
    await state.wait_disconnect()
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
    status.setup(app)
    scheduler.setup(app)
    datastore.setup(app)
    commander_sim.setup(app)
    codec.setup(app)
    device.setup(app)
    seeder.setup(app)
    return app


@pytest.fixture
async def spark_status(app):
    return status.get_status(app)


@pytest.fixture
def store(app):
    return datastore.get_datastore(app)


@pytest.fixture
def api_mock(mocker):
    m = mocker.patch(TESTED + '.object_api.ObjectApi').return_value
    m.read = CoroutineMock()
    m.write = CoroutineMock()
    return m


@pytest.fixture
def config(app):
    return datastore.get_config(app)


async def test_seed_status(app, client, mocker, spark_status):
    await synchronized(app)
    assert states(app) == [False, True, True]

    await disconnect(app)
    assert states(app) == [True, False, False]

    await connect(app)
    assert states(app) == [False, True, True]


async def test_seed_errors(app, client, mocker, api_mock, system_exit_mock):
    await synchronized(app)

    api_mock.read = CoroutineMock(side_effect=RuntimeError)
    await disconnect(app)

    await connect(app)

    assert states(app) == [False, True, False]
    assert system_exit_mock.call_count == 1
    assert not seeder.get_seeder(app).active


async def test_write_error(app, client, mocker, api_mock, system_exit_mock):
    await synchronized(app)
    api_mock.write = CoroutineMock(side_effect=RuntimeError)
    await disconnect(app)
    await connect(app)

    assert states(app) == [False, True, False]
    assert system_exit_mock.call_count == 1
    assert not seeder.get_seeder(app).active


async def test_timeout(app, client, mocker, api_mock, system_exit_mock):
    await synchronized(app)
    await disconnect(app)
    mocker.patch(TESTED + '.HANDSHAKE_TIMEOUT_S', 0.0001)
    s = seeder.get_seeder(app)
    mocker.patch.object(s, '_ping_controller', CoroutineMock())

    await connect(app)
    assert system_exit_mock.call_count == 1
    assert not seeder.get_seeder(app).active
