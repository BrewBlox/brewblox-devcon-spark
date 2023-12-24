"""
Tests brewblox_devcon_spark.api.mqtt_api
"""

import pytest
from brewblox_service import mqtt, scheduler

from brewblox_devcon_spark import (block_store, codec, commander, connection,
                                   controller, exceptions, global_store,
                                   service_store, state_machine,
                                   synchronization)
from brewblox_devcon_spark.api import mqtt_api
from brewblox_devcon_spark.models import Block, BlockIdentity, ServiceConfig

TESTED = mqtt_api.__name__


@pytest.fixture
def setup(app, broker):
    config = utils.get_config()
    config.mqtt_host = 'localhost'
    config.mqtt_port = broker['mqtt']
    config.state_topic = 'test_mqtt/state'

    scheduler.setup(app)
    mqtt.setup(app)
    state_machine.setup(app)
    block_store.setup(app)
    global_store.setup(app)
    service_store.setup(app)
    codec.setup(app)
    connection.setup(app)
    commander.setup(app)
    synchronization.setup(app)
    controller.setup(app)

    mqtt_api.setup(app)


def block_args(app):
    return Block(
        id='testobj',
        serviceId=app['config'].name,
        type='TempSensorOneWire',
        data={
            'value': 12345,
            'offset': 20,
            'address': 'FF'
        }
    )


async def read(app, args: BlockIdentity):
    return await controller.fget(app).read_block(args)


async def test_create(app, client):
    api = mqtt_api.fget(app)
    await api._create('topic', block_args(app).json())

    assert await read(app, BlockIdentity(id='testobj'))


async def test_write(app, client):
    api = mqtt_api.fget(app)
    await api._create('topic', block_args(app).json())
    await api._write('topic', block_args(app).json())

    assert await read(app, BlockIdentity(id='testobj'))


async def test_patch(app, client):
    api = mqtt_api.fget(app)
    await api._create('topic', block_args(app).json())
    await api._patch('topic', block_args(app).json())

    assert await read(app, BlockIdentity(id='testobj'))


async def test_delete(app, client):
    api = mqtt_api.fget(app)
    await api._create('topic', block_args(app).json())
    await api._delete('topic', BlockIdentity(
        id='testobj',
        serviceId=app['config'].name,
    ).json())

    with pytest.raises(exceptions.UnknownId):
        await read(app, BlockIdentity(id='testobj'))


async def test_unknown_service_id(app, client):
    api = mqtt_api.fget(app)

    args = block_args(app)
    args.serviceId = ''
    await api._create('topic', args.json())
    await api._write('topic', args.json())
    await api._patch('topic', args.json())
    await api._delete('topic', args.json())

    with pytest.raises(exceptions.UnknownId):
        await read(app, BlockIdentity(id='testobj'))
