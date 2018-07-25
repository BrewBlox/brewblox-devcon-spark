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
    return 'OneWireTempSensor', {
        'settings': {
            'address': 'ff',
            'offset[delta_degC]': 20
        },
        'state': {
            'value[delta_degC]': 123,
            'connected': True
        }
    }


@pytest.fixture
def app(app):
    """App + controller routes"""
    datastore.setup(app)
    commander_sim.setup(app)
    scheduler.setup(app)
    codec.setup(app)
    device.setup(app)
    return app


@pytest.fixture
def cmder(app):
    return features.get(app, commander.SparkCommander)


@pytest.fixture
def ctrl(app):
    return device.get_controller(app)


@pytest.fixture
async def store(app, client):
    return datastore.get_object_store(app)


def test_setup(app, app_config):
    assert device.get_controller(app).name == app_config['name']


async def test_transcoding(app, client, cmder, store, ctrl, mocker):
    c = codec.get_codec(app)
    obj_type, obj_data = generate_obj()
    enc_type, enc_data = await c.encode(obj_type, obj_data)

    object_args = {
        'object_id': 'alias',
        'profiles': [1],
        'object_type': obj_type,
        'object_data': obj_data
    }

    await store.insert({
        'service_id': 'alias',
        'controller_id': 200
    })

    encode_spy = mocker.spy(c, 'encode')
    decode_spy = mocker.spy(c, 'decode')

    retval = await ctrl.create_object(object_args)
    assert retval['object_data']['settings']['address'] == 'ff'

    encode_spy.assert_called_once_with(obj_type, obj_data)
    decode_spy.assert_called_once_with(enc_type, enc_data)


async def test_list_transcoding(app, client, cmder, store, ctrl, mocker):
    obj_type, obj_data = generate_obj()

    for i in range(5):
        await store.insert({
            'service_id': f'obj{i}',
            'controller_id': 10 + i
        })

        await ctrl.create_object({
            'object_id': f'obj{i}',
            'profiles': [1],
            'object_type': obj_type,
            'object_data': obj_data
        })

    c = codec.get_codec(app)
    decode_spy = mocker.spy(c, 'decode')

    retval = await ctrl.list_saved_objects()
    assert len(retval['objects']) == 5
    assert decode_spy.call_count == 5


async def test_resolve_id(app, client, store, mocker, ctrl):
    random_mock = mocker.patch(TESTED + '.random_string')
    random_mock.return_value = 'totally random string'
    await store.insert_multiple([
        {
            'service_id': 'alias',
            'controller_id': 123
        },
        {
            'service_id': '4-2',
            'controller_id': 24
        }
    ])

    assert await ctrl.find_controller_id(ctrl._object_store, 'alias') == 123
    assert await ctrl.find_controller_id(ctrl._object_store, 840) == 840

    assert await ctrl.find_service_id(ctrl._object_store, 123) == 'alias'
    assert await ctrl.find_service_id(ctrl._object_store, 'testey') == 'testey'
    # Service ID not found: create placeholder
    assert await ctrl.find_service_id(ctrl._object_store, 66) == 'totally random string'


async def test_resolve_links(app, client, store, mocker, ctrl):
    finder_func = CoroutineMock(side_effect=lambda store, val: '|'+str(val))

    data = {
        device.OBJECT_DATA_KEY: {
            'testval': 1,
            'input<>': 2,
            'output<>': 'moo',
            'nested': {
                'flappy<>': 'floppy',
                'meaning_of_life': 42
            }
        }
    }

    output = await ctrl._resolve_links(finder_func, data)

    assert output == data
    assert data == {
        device.OBJECT_DATA_KEY: {
            'testval': 1,
            'input<>': '|2',
            'output<>': '|moo',
            'nested': {
                'flappy<>': '|floppy',
                'meaning_of_life': 42
            }
        }
    }
