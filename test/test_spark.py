"""
Tests brewblox_devcon_spark.spark
"""

import pytest
from brewblox_service import scheduler
from mock import AsyncMock, Mock

from brewblox_devcon_spark import (block_store, codec, commander_sim, const,
                                   exceptions, service_status, spark)
from brewblox_devcon_spark.codec.opts import CodecOpts

TESTED = spark.__name__


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
    service_status.setup(app)
    block_store.setup(app)
    commander_sim.setup(app)
    scheduler.setup(app)
    codec.setup(app)
    spark.setup(app)
    return app


@pytest.fixture
async def store(app, client):
    return block_store.fget(app)


async def test_transcoding(app, client, store):
    s = spark.fget(app)
    c = codec.fget(app)
    obj_type, obj_data = generate_obj()
    enc_type, enc_data = await c.encode(obj_type, obj_data)

    object_args = {
        'id': 'alias',
        'groups': [1],
        'type': obj_type,
        'data': obj_data
    }

    store['alias', 300] = dict()

    c.encode = AsyncMock(wraps=c.encode)
    c.decode = AsyncMock(wraps=c.decode)

    retval = await s.create_object(object_args)
    assert retval['data']['settings']['address'] == 'ff'.rjust(16, '0')

    c.encode.assert_any_await(obj_type, obj_data, opts=CodecOpts())
    c.decode.assert_any_await(enc_type, enc_data, opts=CodecOpts())


async def test_list_transcoding(app, client, store, mocker):
    s = spark.fget(app)
    obj_type, obj_data = generate_obj()
    ids = {f'obj{i}' for i in range(5)}

    for i, id in enumerate(ids):
        store[id, 300+i] = dict()

        await s.create_object({
            'id': id,
            'groups': [0],
            'type': obj_type,
            'data': obj_data
        })

    retval = await s.list_stored_objects()
    assert ids.issubset({obj['id'] for obj in retval['objects']})


async def test_convert_id(app, client, store, mocker):
    store['alias', 123] = dict()
    store['4-2', 24] = dict()

    resolver = spark.SparkResolver(app)
    opts = CodecOpts()

    assert await resolver.convert_sid_nid({'id': 'alias'}, opts) == {'nid': 123}
    assert await resolver.convert_sid_nid({'nid': 840}, opts) == {'nid': 840}
    assert await resolver.convert_sid_nid({'id': 840}, opts) == {'nid': 840}
    # When both present, NID takes precedence
    assert await resolver.convert_sid_nid({'id': 'alias', 'nid': 444}, opts) == {'nid': 444}
    assert await resolver.convert_sid_nid({}, opts) == {}

    assert await resolver.add_sid({'nid': 123}, opts) == {'nid': 123, 'id': 'alias'}
    assert await resolver.add_sid({'id': 'testey'}, opts) == {'id': 'testey'}
    assert await resolver.add_sid({}, opts) == {}

    with pytest.raises(exceptions.DecodeException):
        await resolver.add_sid({'nid': 'testey'}, opts)

    # Service ID not found: create placeholder
    generated = await resolver.add_sid({'nid': 456, 'type': 'Edgecase,driven'}, opts)
    assert generated['id'].startswith(const.GENERATED_ID_PREFIX)
    assert ',driven' not in generated['id']


async def test_resolve_links(app, client, store):
    store['eeney', 9001] = dict()
    store['miney', 9002] = dict()
    store['moo', 9003] = dict()

    def create_data():
        return {
            'data': {
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
                ],
                'metavalue': {
                    '__bloxtype': 'Link',
                    'id': 'eeney',
                },
            },
        }

    resolver = spark.SparkResolver(app)
    output = await resolver.convert_links_nid(create_data(), CodecOpts())

    assert output == {
        'data': {
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
            'metavalue': {
                '__bloxtype': 'Link',
                'id': 9001,
            },
        },
    }

    output = await resolver.convert_links_sid(output, CodecOpts())
    assert output == create_data()


async def test_check_connection(app, client, mocker):
    s = spark.fget(app)
    await s.check_connection()

    m_wait_sync = mocker.patch(TESTED + '.service_status.wait_synchronized', AsyncMock())
    m_wait_sync.return_value = False
    m_cmder = Mock()
    m_cmder.execute = AsyncMock()
    m_cmder.start_reconnect = AsyncMock()
    mocker.patch(TESTED + '.commander.fget').return_value = m_cmder

    await s.check_connection()
    assert m_cmder.execute.await_count == 0
    assert m_cmder.start_reconnect.await_count == 0

    m_wait_sync.return_value = True

    await s.check_connection()
    assert m_cmder.execute.await_count == 1
    assert m_cmder.start_reconnect.await_count == 0

    m_cmder.execute.side_effect = exceptions.CommandException()

    await s.check_connection()
    assert m_cmder.execute.await_count == 2
    assert m_cmder.start_reconnect.await_count == 1


async def test_start_update(app, client):
    service_status.fget(app).set_updating()

    with pytest.raises(exceptions.UpdateInProgress):
        await spark.fget(app).list_objects()
