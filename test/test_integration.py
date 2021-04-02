"""
Integration tests, run against firmware simulator

These tests are marked with pytest.mark.integration, and require the --integration option to run
"""


import asyncio
from shutil import rmtree

import pytest
from brewblox_service import mqtt, scheduler
from brewblox_service.testing import response

from brewblox_devcon_spark import (block_cache, block_store, commander,
                                   connection, global_store, service_status,
                                   service_store, spark, synchronization)
from brewblox_devcon_spark.__main__ import parse_ini
from brewblox_devcon_spark.api import (blocks_api, debug_api, error_response,
                                       settings_api, system_api)
from brewblox_devcon_spark.codec import codec, unit_conversion


@pytest.fixture(scope='module', autouse=True)
def simulator_file_cleanup():
    yield
    rmtree('simulator/', ignore_errors=True)


@pytest.fixture
def app(app):
    app['ini'] = parse_ini(app)
    app['config']['simulation'] = True
    app['config']['volatile'] = True
    app['config']['device_id'] = '123456789012345678901234'

    service_status.setup(app)

    connection.setup(app)
    commander.setup(app)

    scheduler.setup(app)
    mqtt.setup(app)

    global_store.setup(app)
    service_store.setup(app)
    block_store.setup(app)
    block_cache.setup(app)
    unit_conversion.setup(app)
    codec.setup(app)
    spark.setup(app)

    error_response.setup(app)
    debug_api.setup(app)
    blocks_api.setup(app)
    system_api.setup(app)
    settings_api.setup(app)

    synchronization.setup(app)
    return app


@pytest.fixture(autouse=True)
async def wait_sync(app, client):
    await asyncio.wait_for(service_status.wait_synchronized(app), 5)


@pytest.mark.integration
async def test_ping(app, client):
    await response(client.post('/system/ping'))


@pytest.mark.integration
async def test_create_read(app, client):
    await response(client.post('/blocks/create', json={
        'id': 'sensor-1',
        'groups': [0],
        'type': 'TempSensorMock',
        'data': {
            'value[celsius]': 20.89789201,
            'connected': True
        }
    }), 201)
    obj = await response(client.post('/blocks/read', json={'id': 'sensor-1'}))
    assert obj['id'] == 'sensor-1'
    assert obj['data']
