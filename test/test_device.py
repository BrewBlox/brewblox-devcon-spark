"""
Tests brewblox_devcon_spark.device
"""

import pytest
from brewblox_devcon_spark import device, commander, datastore
from brewblox_codec_spark import codec
from asynctest import CoroutineMock


TESTED = device.__name__


@pytest.fixture
def commander_mock(mocker, loop):
    cmder = commander.SparkCommander(loop=loop)

    def echo(command):
        retval = command.decoded_request
        retval['command'] = command.name
        return retval

    cmder.bind = CoroutineMock()
    cmder.close = CoroutineMock()
    cmder.execute = CoroutineMock(side_effect=echo)
    return cmder


@pytest.fixture
async def store(loop):
    store = datastore.MemoryDataStore()
    await store.start(loop=loop)
    return store


@pytest.fixture
async def app(app, commander_mock, store, mocker):
    """App + controller routes"""
    mocker.patch(TESTED + '.SparkCommander').return_value = commander_mock
    mocker.patch(TESTED + '.FileDataStore').return_value = store
    device.setup(app)
    return app


def test_setup(app, app_config):
    assert device.get_controller(app).name == app_config['name']


async def test_start_close(app, client, commander_mock):
    assert commander_mock.bind.call_count == 1
    assert commander_mock.close.call_count == 0

    controller = device.get_controller(app)

    await controller.close()
    await controller.close()

    await controller.start(app)
    assert commander_mock.bind.call_count == 2

    await controller.start(app)
    assert commander_mock.bind.call_count == 3

    # should not trigger errors in app cleanup
    await controller.close()


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
