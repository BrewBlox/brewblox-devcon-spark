"""
Tests brewblox_devcon_spark.device
"""

import pytest
from asynctest import CoroutineMock
from brewblox_codec_spark import codec
from brewblox_devcon_spark import commander, datastore, device
from brewblox_service import features

TESTED = device.__name__


@pytest.fixture
def commander_mock(mocker):
    cmder = commander.SparkCommander(app=None)

    def echo(command):
        retval = command.decoded_request
        retval['command'] = command.name
        return retval

    cmder.start = CoroutineMock()
    cmder.close = CoroutineMock()
    cmder.execute = CoroutineMock(side_effect=echo)
    return cmder


@pytest.fixture
def app(app, commander_mock):
    """App + controller routes"""
    features.add(app, commander_mock, name=commander.SparkCommander)

    features.add(app, datastore.MemoryDataStore(), name='object_store')
    features.add(app, datastore.MemoryDataStore(), name='object_cache')
    features.add(app, datastore.MemoryDataStore(), name='system_store')

    device.setup(app)
    return app


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
    encoded = codec.encode(obj_type, obj)
    obj = codec.decode(obj_type, encoded)

    retval = await controller.write_value(
        id='alias',
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


async def test_resolve_id(app, client, commander_mock, store):
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
    assert await ctrl.resolve_service_id(ctrl._object_store, [6, 6, 6]) == '6-6-6'
    # Placeholder service ID already taken - degrade to controller ID
    assert await ctrl.resolve_service_id(ctrl._object_store, [4, 2]) == [4, 2]
