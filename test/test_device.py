"""
Tests brewblox_devcon_spark.device
"""

import pytest
from asynctest import CoroutineMock
from brewblox_service import features, scheduler

from brewblox_codec_spark import codec
from brewblox_devcon_spark import commander, commander_sim, datastore, device

TESTED = device.__name__


def generate_obj():
    return 'OneWireTempSensor', dict(
        settings=dict(
            address='ff',
            offset=20
        ),
        state=dict(
            value=12345,
            connected=True
        )
    )


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

    c = codec.get_codec(app)
    encoded_type, encoded = await c.encode(*generate_obj())
    decoded_type, decoded = await c.decode(encoded_type, encoded)

    retval = await controller.write_value(
        object_id='alias',
        object_type=decoded_type,
        object_size=0,
        object_data=decoded
    )
    assert retval['object_data'] == decoded


async def test_list_transcoding(app, client, commander_mock, store):
    controller = device.get_controller(app)
    c = codec.get_codec(app)

    await store.insert({
        'service_id': 'alias',
        'controller_id': [1, 2, 3]
    })

    encoded_type, encoded = await c.encode(*generate_obj())
    decoded_type, decoded = await c.decode(encoded_type, encoded)

    # Test correct processing of lists of objects
    commander_mock.execute = CoroutineMock(return_value=dict(
        objects=[
            # Call dict twice to avoid populating the list with references to the same dict
            dict(object_type=encoded_type, object_data=encoded) for _ in range(2)
        ]
    ))
    retval = await controller.write_value(
        object_id='alias',
        object_type=decoded_type,
        object_size=0,
        object_data=decoded
    )
    assert retval['objects'] == [dict(object_type=decoded_type, object_data=decoded)] * 2


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

    assert await ctrl.find_controller_id(ctrl._object_store, 'alias') == [1, 2, 3]
    assert await ctrl.find_controller_id(ctrl._object_store, [8, 4, 0]) == [8, 4, 0]

    assert await ctrl.find_service_id(ctrl._object_store, [1, 2, 3]) == 'alias'
    assert await ctrl.find_service_id(ctrl._object_store, 'testey') == 'testey'
    # Service ID not found: create placeholder
    assert await ctrl.find_service_id(ctrl._object_store, [6, 6, 6]) == 'totally random string'
