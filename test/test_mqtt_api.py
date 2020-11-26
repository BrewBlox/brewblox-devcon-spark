"""
Tests brewblox_devcon_spark.api.mqtt_api
"""

import pytest
from brewblox_service import scheduler
from mock import AsyncMock

from brewblox_devcon_spark import (block_cache, block_store, commander_sim,
                                   config_store, exceptions, service_status,
                                   spark, synchronization)
from brewblox_devcon_spark.api import blocks_api, mqtt_api
from brewblox_devcon_spark.codec import codec, unit_conversion

TESTED = mqtt_api.__name__


@pytest.fixture(autouse=True)
def m_publish(mocker):
    m = mocker.patch(blocks_api.__name__ + '.mqtt.publish', AsyncMock())
    return m


@pytest.fixture(autouse=True)
def m_mqtt(mocker):
    mocker.patch(TESTED + '.mqtt.listen', AsyncMock())
    mocker.patch(TESTED + '.mqtt.subscribe', AsyncMock())
    mocker.patch(TESTED + '.mqtt.unlisten', AsyncMock())
    mocker.patch(TESTED + '.mqtt.unsubscribe', AsyncMock())


@pytest.fixture
async def app(app, loop):
    """App + controller routes"""
    service_status.setup(app)
    scheduler.setup(app)
    commander_sim.setup(app)
    block_store.setup(app)
    block_cache.setup(app)
    config_store.setup(app)
    unit_conversion.setup(app)
    codec.setup(app)
    synchronization.setup(app)
    spark.setup(app)

    mqtt_api.setup(app)

    return app


def block_args(app):
    return {
        'serviceId': app['config']['name'],
        'id': 'testobj',
        'groups': [0],
        'type': 'TempSensorOneWire',
        'data': {
            'value': 12345,
            'offset': 20,
            'address': 'FF'
        }
    }


async def read(app, args):
    return await blocks_api.BlocksApi(app).read(args)


async def test_create(app, client):
    api = mqtt_api.fget(app)
    await api._create('topic', block_args(app))

    assert await read(app, {'id': block_args(app)['id']})


async def test_write(app, client):
    api = mqtt_api.fget(app)
    await api._create('topic', block_args(app))
    await api._write('topic', block_args(app))

    assert await read(app, {'id': block_args(app)['id']})


async def test_patch(app, client):
    api = mqtt_api.fget(app)
    await api._create('topic', block_args(app))
    await api._patch('topic', block_args(app))

    assert await read(app, {'id': block_args(app)['id']})


async def test_delete(app, client):
    api = mqtt_api.fget(app)
    await api._create('topic', block_args(app))
    await api._delete('topic', {
        'serviceId': block_args(app)['serviceId'],
        'id': block_args(app)['id']
    })

    with pytest.raises(exceptions.UnknownId):
        await read(app, {'id': block_args(app)['id']})


async def test_validate_err(app, client):
    api = mqtt_api.fget(app)

    await api._create('topic', {})
    with pytest.raises(exceptions.UnknownId):
        await read(app, {'id': block_args(app)['id']})

    await api._create('topic', block_args(app))

    updated_args = block_args(app)
    updated_args['groups'] == [0, 1]
    await api._write('topic', {})

    actual = await read(app, {'id': block_args(app)['id']})
    assert actual['groups'] == [0]

    await api._delete('topic', {})
    await read(app, {'id': block_args(app)['id']})


async def test_unknown_service_id(app, client):
    api = mqtt_api.fget(app)

    def other_args():
        return {**block_args(app), 'serviceId': 'timbuktu'}

    await api._create('topic', other_args())
    with pytest.raises(exceptions.UnknownId):
        await read(app, {'id': block_args(app)['id']})

    await api._create('topic', block_args(app))

    updated_args = other_args()
    updated_args['groups'] == [0, 1]
    await api._write('topic', other_args())

    actual = await read(app, {'id': block_args(app)['id']})
    assert actual['groups'] == [0]

    await api._delete('topic', other_args())
    await read(app, {'id': block_args(app)['id']})
