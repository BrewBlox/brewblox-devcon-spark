"""
Tests brewblox_devcon_spark.device
"""

import pytest
from brewblox_service import features, scheduler

from brewblox_codec_spark import codec
from brewblox_devcon_spark import (commander, commander_sim, device, status,
                                   twinkeydict)
from brewblox_devcon_spark.device import OBJECT_DATA_KEY, OBJECT_ID_KEY

TESTED = device.__name__


def generate_obj():
    return 'EdgeCase', {
        'settings': {
            'address': 'ff',
            'offset[delta_degC]': 20
        },
        'state': {
            'value[delta_degC]': 123,
            'connected': True
        },
        'link<>': 30,
        'additionalLinks': [
            {'connection<>': 1},
            {'connection<>': 2},
        ]
    }


@pytest.fixture
def app(app):
    """App + controller routes"""
    status.setup(app)
    twinkeydict.setup(app)
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
    return twinkeydict.get_object_store(app)


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

    store['alias', 200] = dict()

    encode_spy = mocker.spy(c, 'encode')
    decode_spy = mocker.spy(c, 'decode')

    retval = await ctrl.create_object(object_args)
    assert retval['object_data']['settings']['address'] == 'ff'

    encode_spy.assert_called_once_with(obj_type, obj_data)
    decode_spy.assert_called_once_with(enc_type, enc_data)


async def test_list_transcoding(app, client, cmder, store, ctrl, mocker):
    obj_type, obj_data = generate_obj()

    for i in range(5):
        store[f'obj{i}', 10+i] = dict()

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
    store['alias', 123] = dict()
    store['4-2', 24] = dict()

    resolver = device.SparkResolver(app)

    assert await resolver.resolve_controller_id({OBJECT_ID_KEY: 'alias'}) == {OBJECT_ID_KEY: 123}
    assert await resolver.resolve_controller_id({OBJECT_ID_KEY: 840}) == {OBJECT_ID_KEY: 840}

    assert await resolver.resolve_service_id({OBJECT_ID_KEY: 123}) == {OBJECT_ID_KEY: 'alias'}
    assert await resolver.resolve_service_id({OBJECT_ID_KEY: 'testey'}) == {OBJECT_ID_KEY: 'testey'}

    # Service ID not found: create placeholder
    generated = await resolver.resolve_service_id({OBJECT_ID_KEY: 456})
    assert generated[OBJECT_ID_KEY].startswith('generated|')


async def test_resolve_links(app, client, store):
    store['eeney', 9001] = dict()
    store['miney', 9002] = dict()
    store['moo', 9003] = dict()

    def create_data():
        return {
            OBJECT_DATA_KEY: {
                'testval': 1,
                'input<>': 'eeney',
                'output<>': 'miney',
                'nested': {
                    'flappy<>': 'moo',
                    'meaning_of_life': 42,
                    'mystery<>': None
                }
            }
        }

    resolver = device.SparkResolver(app)
    output = await resolver.resolve_controller_links(create_data())

    assert output == {
        OBJECT_DATA_KEY: {
            'testval': 1,
            'input<>': 9001,
            'output<>': 9002,
            'nested': {
                'flappy<>': 9003,
                'meaning_of_life': 42,
                'mystery<>': 0
            }
        }
    }

    output = await resolver.resolve_service_links(output)
    assert output == create_data()
