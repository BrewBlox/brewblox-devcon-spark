"""
Tests brewblox_devcon_spark.seeder
"""

import asyncio

import pytest
from asynctest import CoroutineMock
from brewblox_service import scheduler

from brewblox_devcon_spark import (commander_sim, datastore, device, seeder,
                                   status)
from brewblox_devcon_spark.codec import codec

TESTED = seeder.__name__


def states(app):
    state = status.get_status(app)
    return [
        state.disconnected.is_set(),
        state.connected.is_set(),
        state.synchronized.is_set(),
    ]


async def connect(app):
    state = status.get_status(app)
    state.disconnected.clear()
    state.connected.set()
    await asyncio.sleep(0.01)


async def disconnect(app):
    state = status.get_status(app)
    state.connected.clear()
    state.disconnected.set()
    await asyncio.sleep(0.01)


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
def config(app):
    return datastore.get_config(app)


async def test_seed_calls(app, client, mocker, spark_status, store, config):
    store_spy = mocker.spy(store, 'read')
    config_spy = mocker.spy(config, 'read')

    assert states(app) == [False, True, True]

    await disconnect(app)
    assert states(app) == [True, False, False]

    await connect(app)
    assert states(app) == [False, True, True]
    assert store_spy.call_count == 1
    assert config_spy.call_count == 1


async def test_seed_errors(app, client, mocker):
    api_mock = mocker.patch(TESTED + '.object_api.ObjectApi').return_value

    api_mock.read = CoroutineMock(side_effect=RuntimeError)
    await disconnect(app)

    with pytest.warns(UserWarning, match='Failed to seed datastore'):
        await connect(app)

    assert states(app) == [False, True, True]
    assert seeder.get_seeder(app).active

    api_mock.read = CoroutineMock()
    api_mock.write = CoroutineMock(side_effect=RuntimeError)
    await disconnect(app)

    with pytest.warns(UserWarning, match='Failed to seed controller time'):
        await connect(app)

    assert states(app) == [False, True, True]
    assert seeder.get_seeder(app).active


async def test_cancel_datastore(app, client, mocker):
    api_mock = mocker.patch(TESTED + '.object_api.ObjectApi').return_value
    api_mock.read = CoroutineMock(side_effect=asyncio.CancelledError)

    await disconnect(app)
    await connect(app)

    assert states(app) == [False, True, False]
    assert not seeder.get_seeder(app).active


async def test_cancel_time(app, client, mocker):
    api_mock = mocker.patch(TESTED + '.object_api.ObjectApi').return_value
    api_mock.write = CoroutineMock(side_effect=asyncio.CancelledError)

    await disconnect(app)
    await connect(app)

    assert states(app) == [False, True, False]
    assert not seeder.get_seeder(app).active
