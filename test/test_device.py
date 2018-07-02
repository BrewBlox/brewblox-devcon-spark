"""
Tests brewblox_devcon_spark.device
"""

import pytest
from asynctest import CoroutineMock
from brewblox_codec_spark import codec
from brewblox_devcon_spark import commander, commander_sim, datastore, device
from brewblox_service import features, scheduler

TESTED = device.__name__


@pytest.fixture
def app(app):
    """App + controller routes"""
    cmder = commander_sim.SimulationCommander(app)

    def echo(command):
        retval = command.decoded_request
        retval['command'] = command.name
        return retval

    features.add(app, cmder, key=commander.SparkCommander)
    features.add(app, datastore.MemoryDataStore(app), key='object_store')
    features.add(app, datastore.MemoryDataStore(app), key='object_cache')
    features.add(app, datastore.MemoryDataStore(app), key='system_store')

    scheduler.setup(app)
    codec.setup(app)
    device.setup(app)
    return app


@pytest.fixture
def commander_mock(app):
    return features.get(app, commander.SparkCommander)


@pytest.fixture
async def store(app, client):
    return datastore.get_object_store(app)


def test_setup(app, app_config):
    assert device.get_controller(app).name == app_config['name']


async def test_transcoding(app, client, commander_mock, store):
    controller = device.get_controller(app)
    await store.insert({
        'service_id': 'alias',
        'controller_id': [1, 2, 3]
    })

    # OneWireTempSensor
    obj_type = 6
    obj = dict(
        settings=dict(
            address='ff',
            offset=20
        ),
        state=dict(
            value=12345,
            connected=True
        )
    )
    c = codec.get_codec(app)
    encoded = await c.encode(obj_type, obj)
    obj = await c.decode(obj_type, encoded)

    retval = await controller.write_value(
        object_id='alias',
        object_type=obj_type,
        object_size=0,
        object_data=obj
    )
    assert retval['object_data'] == obj

    # Test correct processing of lists of objects
    commander_mock.execute = CoroutineMock(return_value=dict(
        objects=[
            # Call dict twice to avoid populating the list with references to the same dict
            dict(object_type=obj_type, object_data=encoded),
            dict(object_type=obj_type, object_data=encoded),
        ]
    ))
    retval = await controller.write_value(
        object_id='alias',
        object_type=obj_type,
        object_size=0,
        object_data=obj
    )
    assert retval['objects'] == [dict(object_type=obj_type, object_data=obj)] * 2


async def test_resolve_id(app, client, store, mocker):
    random_mock = mocker.patch(TESTED + '.random_string')
    random_mock.return_value = 'totally random string'
    await store.insert_multiple([
        {
            'service_id': 'alias',
            'controller_id': [1, 2, 3]
        },
        {
            'service_id': '4-2',
            'controller_id': [2, 4]
        }
    ])

    ctrl = device.get_controller(app)

    assert await ctrl.resolve_controller_id(ctrl._object_store, 'alias') == [1, 2, 3]
    assert await ctrl.resolve_controller_id(ctrl._object_store, [8, 4, 0]) == [8, 4, 0]

    assert await ctrl.resolve_service_id(ctrl._object_store, [1, 2, 3]) == 'alias'
    assert await ctrl.resolve_service_id(ctrl._object_store, 'testey') == 'testey'
    # Service ID not found: create placeholder
    assert await ctrl.resolve_service_id(ctrl._object_store, [6, 6, 6]) == 'totally random string'
