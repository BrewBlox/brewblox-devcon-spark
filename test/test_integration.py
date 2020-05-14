"""
Integration tests, run against firmware simulator

These tests are marked with pytest.mark.integration, and require the --integration option to run
"""


import asyncio
from shutil import rmtree
from unittest.mock import patch

import pytest
from brewblox_service import events, scheduler
from brewblox_service.testing import response

from brewblox_devcon_spark import (commander, communication, datastore, device,
                                   simulator, state, synchronization)
from brewblox_devcon_spark.__main__ import parse_ini
from brewblox_devcon_spark.api import (alias_api, debug_api, error_response,
                                       object_api, settings_api, system_api)
from brewblox_devcon_spark.codec import codec, unit_conversion

DEVICE_ID = '123456789012345678901234'


@pytest.fixture(scope='module', autouse=True)
def firmware_sim():
    with patch(communication.__name__ + '.RETRY_INTERVAL_S', 0.1):
        sim = simulator.FirmwareSimulator()
        sim.start(DEVICE_ID)
        yield
        sim.stop()
        rmtree('simulator/', ignore_errors=True)


@pytest.fixture
def app(app):
    app['ini'] = parse_ini(app)
    config = app['config']
    config['device_id'] = DEVICE_ID
    config['device_host'] = 'localhost'
    config['device_port'] = 8332
    config['device_serial'] = None
    config['simulation'] = True
    config['volatile'] = True

    state.setup(app)

    communication.setup(app)
    commander.setup(app)

    scheduler.setup(app)
    events.setup(app)

    datastore.setup(app)
    unit_conversion.setup(app)
    codec.setup(app)
    device.setup(app)

    error_response.setup(app)
    debug_api.setup(app)
    alias_api.setup(app)
    object_api.setup(app)
    system_api.setup(app)
    settings_api.setup(app)

    synchronization.setup(app)
    return app


@pytest.fixture(autouse=True)
async def wait_sync(app, client):
    await asyncio.wait_for(state.wait_synchronize(app), 5)


@pytest.mark.integration
async def test_ping(app, client):
    await response(client.get('/system/ping'))


@pytest.mark.integration
async def test_create_read(app, client):
    await response(client.post('/objects', json={
        'id': 'sensor-1',
        'groups': [0],
        'type': 'TempSensorMock',
        'data': {
            'value[celsius]': 20.89789201,
            'connected': True
        }
    }))
    obj = await response(client.get('/objects/sensor-1'))
    assert obj['id'] == 'sensor-1'
    assert obj['data']
