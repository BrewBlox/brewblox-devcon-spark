"""
Tests brewblox_devcon_spark.api.mqtt_api
"""

import pytest
from brewblox_service import scheduler

from brewblox_devcon_spark import (block_store, codec, commander, connection,
                                   controller, exceptions, global_store,
                                   service_status, service_store,
                                   synchronization)
from brewblox_devcon_spark.api import mqtt_api
from brewblox_devcon_spark.models import Block, BlockIdentity

TESTED = mqtt_api.__name__


@pytest.fixture(autouse=True)
def m_mqtt(mocker):
    mocker.patch(TESTED + '.mqtt', autospec=True)


@pytest.fixture
async def app(app, event_loop):
    """App + controller routes"""
    scheduler.setup(app)
    service_status.setup(app)
    block_store.setup(app)
    global_store.setup(app)
    service_store.setup(app)
    codec.setup(app)
    connection.setup(app)
    commander.setup(app)
    synchronization.setup(app)
    controller.setup(app)

    mqtt_api.setup(app)

    return app


def block_args(app):
    return Block(
        id='testobj',
        serviceId=app['config']['name'],
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
    await api._create('topic', block_args(app).dict())

    assert await read(app, BlockIdentity(id='testobj'))


async def test_write(app, client):
    api = mqtt_api.fget(app)
    await api._create('topic', block_args(app).dict())
    await api._write('topic', block_args(app).dict())

    assert await read(app, BlockIdentity(id='testobj'))


async def test_patch(app, client):
    api = mqtt_api.fget(app)
    await api._create('topic', block_args(app).dict())
    await api._patch('topic', block_args(app).dict())

    assert await read(app, BlockIdentity(id='testobj'))


async def test_delete(app, client):
    api = mqtt_api.fget(app)
    await api._create('topic', block_args(app).dict())
    await api._delete('topic', BlockIdentity(
        id='testobj',
        serviceId=app['config']['name'],
    ).dict())

    with pytest.raises(exceptions.UnknownId):
        await read(app, BlockIdentity(id='testobj'))


async def test_unknown_service_id(app, client):
    api = mqtt_api.fget(app)

    args = block_args(app)
    args.serviceId = ''
    await api._create('topic', args.dict())
    await api._write('topic', args.dict())
    await api._patch('topic', args.dict())
    await api._delete('topic', args.dict())

    with pytest.raises(exceptions.UnknownId):
        await read(app, BlockIdentity(id='testobj'))
