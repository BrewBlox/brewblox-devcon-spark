"""
Tests brewblox_devcon_spark.seeder
"""

import asyncio
import json
from tempfile import NamedTemporaryFile

import pytest
from brewblox_service import scheduler

from brewblox_devcon_spark import (commander_sim, datastore, device, seeder,
                                   status)
from brewblox_devcon_spark.api import object_api, system_api
from brewblox_devcon_spark.codec import codec

TESTED = seeder.__name__


@pytest.fixture
def seeds():
    return [
        {
            'id': 'tempsensor',
            'profiles': [3],
            'type': 'TempSensorOneWire',
            'data': {
                'address': 'deadbeef',
                'offset[delta_degF]': 20,
            }
        },
        {
            'id': 'boxy',
            'profiles': [7],
            'type': 'XboxController',
            'data': {
                'buttons': {
                    'a': 1,
                    'x': 1,
                    'guide': 1,
                },
                'leftStick': {
                    'x': 100,
                    'y': -500,
                    'click': 1,
                },
                'rightStick': {
                    'x': 1000,
                },
                'dPad': {
                    'up': 1,
                },
                'leftTrigger': 42,
            }
        },
        {
            # Invalid object
            'id': 'MoonMoon',
        }
    ]


@pytest.fixture
def seeds_file(seeds):
    f = NamedTemporaryFile(mode='w+t', encoding='utf8')
    json.dump(seeds, f)
    f.flush()
    yield f.name
    f.close()


@pytest.fixture
async def app(app, seeds_file):
    app['config']['seed_objects'] = seeds_file
    app['config']['seed_profiles'] = [1, 3, 7]

    status.setup(app)
    scheduler.setup(app)
    datastore.setup(app)
    commander_sim.setup(app)
    codec.setup(app)
    device.setup(app)
    seeder.setup(app)
    system_api.setup(app)
    return app


@pytest.fixture
async def noseed_app(app):
    app['config']['seed_objects'] = None
    app['config']['seed_profiles'] = []
    return app


@pytest.fixture
async def errfile_app(app):
    app['config']['seed_objects'] = 'wabberjocky'
    return app


@pytest.fixture
async def errprofiles_app(app):
    app['config']['seed_profiles'] = [10]
    return app


@pytest.fixture
async def spark_status(app):
    return status.get_status(app)


async def test_seeding(app, client, seeds, spark_status, seeds_file):
    oapi = object_api.ObjectApi(app)
    assert spark_status.connected.is_set()
    assert not spark_status.disconnected.is_set()
    assert seeder.get_seeder(app)

    await asyncio.sleep(0.1)
    read_ids = {obj['id'] for obj in await oapi.all()}
    assert read_ids & {'tempsensor', 'boxy'}

    # Test time
    t = await oapi.read('__time')
    assert t['data']['secondsSinceEpoch'] > 100


async def test_reseed(app, client, seeds, spark_status):
    oapi = object_api.ObjectApi(app)

    await asyncio.sleep(0.1)
    await oapi.delete('boxy')
    read_ids = {obj['id'] for obj in await oapi.all()}
    assert 'boxy' not in read_ids

    spark_status.connected.clear()
    spark_status.disconnected.set()
    spark_status.disconnected.clear()
    spark_status.connected.set()

    await asyncio.sleep(0.1)
    await oapi.read('boxy')


async def test_noseed(noseed_app, client):
    await asyncio.sleep(0.1)
    assert 'boxy' not in {
        obj['id'] for obj
        in await object_api.ObjectApi(noseed_app).all()
    }


async def test_errfile(errfile_app, client):
    oapi = object_api.ObjectApi(errfile_app)
    sapi = system_api.SystemApi(errfile_app)

    await asyncio.sleep(0.1)
    # objects not seeded
    assert 'boxy' not in {
        obj['id'] for obj
        in await oapi.all()
    }
    # profiles still ok
    assert await sapi.read_profiles() == [1, 3, 7]


async def test_errprofiles(errprofiles_app, client):
    oapi = object_api.ObjectApi(errprofiles_app)
    sapi = system_api.SystemApi(errprofiles_app)

    await asyncio.sleep(0.1)
    # objects ok
    assert 'boxy' in {
        obj['id'] for obj
        in await oapi.all_stored()
    }
    # profiles default
    assert await sapi.read_profiles() == [0]
