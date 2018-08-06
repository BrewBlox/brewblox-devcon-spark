"""
Tests brewblox_devcon_spark.seeder
"""

import asyncio
import json
from tempfile import NamedTemporaryFile

import pytest
from brewblox_service import scheduler

from brewblox_codec_spark import codec
from brewblox_devcon_spark import (commander_sim, device, seeder, status,
                                   twinkeydict)
from brewblox_devcon_spark.api import object_api, profile_api

TESTED = seeder.__name__


@pytest.fixture
def seeds():
    return [
        {
            'id': 'tempsensor',
            'profiles': [1, 7],
            'type': 'OneWireTempSensor',
            'data': {
                'settings': {
                    'address': 'deadbeef',
                    'offset[delta_degF]': 20
                }
            }
        },
        {
            'id': 'boxy',
            'profiles': [3],
            'type': 'XboxController',
            'data': {
                'buttons': {
                    'a': 1,
                    'x': 1,
                    'guide': 1
                },
                'leftStick': {
                    'x': 100,
                    'y': -500,
                    'click': 1
                },
                'rightStick': {
                    'x': 1000
                },
                'dPad': {
                    'up': 1
                },
                'leftTrigger': 42
            }
        },
        {
            'id': 'MoonMoon'
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
    twinkeydict.setup(app)
    commander_sim.setup(app)
    codec.setup(app)
    device.setup(app)
    seeder.setup(app)
    return app


@pytest.fixture
async def spark_status(app):
    return status.get_status(app)


async def test_seeding(app, client, seeds, spark_status):
    assert spark_status.connected.is_set()
    assert not spark_status.disconnected.is_set()

    assert await profile_api.ProfileApi(app).read_active() == [1, 3, 7]
    read_ids = {obj['id'] for obj in await object_api.ObjectApi(app).list_active()}
    assert read_ids == {
        'tempsensor',
        'boxy'
    }


async def test_reseed(app, client, seeds, spark_status):
    sdr = seeder.get_seeder(app)
    oapi = object_api.ObjectApi(app)
    papi = profile_api.ProfileApi(app)

    await oapi.delete('boxy')
    assert len(await oapi.list_active()) == 1
    await papi.write_active([1])

    # If no profiles are set, then nothing should be written to controller
    sdr._profiles = []

    spark_status.connected.clear()
    spark_status.disconnected.set()
    spark_status.disconnected.clear()
    spark_status.connected.set()

    await asyncio.sleep(0.1)
    await oapi.read('boxy')
    assert await papi.read_active() == [1]
