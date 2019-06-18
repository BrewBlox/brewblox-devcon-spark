"""
Tests brewblox_devcon_spark.device
"""

import pytest
from brewblox_service import features, scheduler

from brewblox_devcon_spark import (commander, commander_sim, datastore, device,
                                   exceptions, status)
from brewblox_devcon_spark.codec import codec
from brewblox_devcon_spark.device import (GENERATED_ID_PREFIX, GROUP_LIST_KEY,
                                          OBJECT_DATA_KEY, OBJECT_LIST_KEY,
                                          OBJECT_NID_KEY, OBJECT_SID_KEY,
                                          OBJECT_TYPE_KEY)

TESTED = device.__name__


def generate_obj():
    return 'EdgeCase', {
        'settings': {
            'address': 'ff'.rjust(16, '0'),
            'offset[delta_degC]': 20
        },
        'state': {
            'value[delta_degC]': 123,
            'connected': True
        },
        'link<ActuatorAnalogInterface>': 30,
        'additionalLinks': [
            {'connection<TempSensorInterface>': 1},
            {'connection<TempSensorInterface>': 2},
        ],
        'listValues': [1, 2, 3],
    }


@pytest.fixture
def app(app):
    """App + controller routes"""
    status.setup(app)
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
    return datastore.get_datastore(app)


async def test_transcoding(app, client, cmder, store, ctrl, mocker):
    c = codec.get_codec(app)
    obj_type, obj_data = generate_obj()
    enc_type, enc_data = await c.encode(obj_type, obj_data)

    object_args = {
        OBJECT_SID_KEY: 'alias',
        GROUP_LIST_KEY: [1],
        OBJECT_TYPE_KEY: obj_type,
        OBJECT_DATA_KEY: obj_data
    }

    store['alias', 300] = dict()

    encode_spy = mocker.spy(c, 'encode')
    decode_spy = mocker.spy(c, 'decode')

    retval = await ctrl.create_object(object_args)
    assert retval[OBJECT_DATA_KEY]['settings']['address'] == 'ff'.rjust(16, '0')

    encode_spy.assert_any_call(obj_type, obj_data, None)
    decode_spy.assert_any_call(enc_type, enc_data, None)


async def test_list_transcoding(app, client, cmder, store, ctrl, mocker):
    obj_type, obj_data = generate_obj()
    ids = {f'obj{i}' for i in range(5)}

    for i, id in enumerate(ids):
        store[id, 300+i] = dict()

        await ctrl.create_object({
            OBJECT_SID_KEY: id,
            GROUP_LIST_KEY: [0],
            OBJECT_TYPE_KEY: obj_type,
            OBJECT_DATA_KEY: obj_data
        })

    retval = await ctrl.list_stored_objects()
    assert ids.issubset({obj[OBJECT_SID_KEY] for obj in retval[OBJECT_LIST_KEY]})


async def test_convert_id(app, client, store, mocker, ctrl):
    store['alias', 123] = dict()
    store['4-2', 24] = dict()

    resolver = device.SparkResolver(app)

    assert await resolver.convert_sid_nid({OBJECT_SID_KEY: 'alias'}) == {OBJECT_NID_KEY: 123}
    assert await resolver.convert_sid_nid({OBJECT_NID_KEY: 840}) == {OBJECT_NID_KEY: 840}
    assert await resolver.convert_sid_nid({OBJECT_SID_KEY: 840}) == {OBJECT_NID_KEY: 840}
    assert await resolver.convert_sid_nid({}) == {}

    assert await resolver.add_sid({OBJECT_NID_KEY: 123}) == {OBJECT_NID_KEY: 123, OBJECT_SID_KEY: 'alias'}
    assert await resolver.add_sid({OBJECT_SID_KEY: 'testey'}) == {OBJECT_SID_KEY: 'testey'}
    assert await resolver.add_sid({}) == {}

    with pytest.raises(exceptions.DecodeException):
        await resolver.add_sid({OBJECT_NID_KEY: 'testey'})

    # Service ID not found: create placeholder
    generated = await resolver.add_sid({OBJECT_NID_KEY: 456, OBJECT_TYPE_KEY: 'Edgecase,driven'})
    assert generated[OBJECT_SID_KEY].startswith(GENERATED_ID_PREFIX)
    assert ',driven' not in generated[OBJECT_SID_KEY]


async def test_resolve_links(app, client, store):
    store['eeney', 9001] = dict()
    store['miney', 9002] = dict()
    store['moo', 9003] = dict()

    def create_data():
        return {
            OBJECT_DATA_KEY: {
                'testval': 1,
                'input<ProcessValueInterface>': 'eeney',
                'output<ProcessValueInterface>': 'miney',
                'nested': {
                    'flappy<>': 'moo',
                    'meaning_of_life': 42,
                    'mystery<EdgeCase>': None
                },
                'listed': [
                    {'flappy<SetpointSensorPairInterface>': 'moo'}
                ]
            }
        }

    resolver = device.SparkResolver(app)
    output = await resolver.convert_links_nid(create_data())

    assert output == {
        OBJECT_DATA_KEY: {
            'testval': 1,
            'input<ProcessValueInterface>': 9001,
            'output<ProcessValueInterface>': 9002,
            'nested': {
                'flappy<>': 9003,
                'meaning_of_life': 42,
                'mystery<EdgeCase>': 0,
            },
            'listed': [
                {'flappy<SetpointSensorPairInterface>': 9003},
            ],
        },
    }

    output = await resolver.convert_links_sid(output)
    assert output == create_data()
