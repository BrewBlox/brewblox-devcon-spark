"""
Tests brewblox_devcon_spark.api
"""

import asyncio

import pytest
from brewblox_service import scheduler

from brewblox_codec_spark import codec
from brewblox_devcon_spark import commander_sim, device, twinkeydict
from brewblox_devcon_spark.api import (alias_api, debug_api, error_response,
                                       object_api, profile_api, system_api)
from brewblox_devcon_spark.api.object_api import (API_DATA_KEY, API_ID_KEY,
                                                  API_TYPE_KEY,
                                                  OBJECT_DATA_KEY,
                                                  OBJECT_TYPE_KEY,
                                                  PROFILE_LIST_KEY)


@pytest.fixture
def object_args():
    return {
        API_ID_KEY: 'testobj',
        PROFILE_LIST_KEY: [1, 4, 7],
        API_TYPE_KEY: 'OneWireTempSensor',
        API_DATA_KEY: {
            'settings': {
                'address': 'FF',
                'offset': 20
            },
            'state': {
                'value': 12345,
                'connected': True
            }
        }
    }


@pytest.fixture
async def app(app, loop):
    """App + controller routes"""
    scheduler.setup(app)
    commander_sim.setup(app)
    twinkeydict.setup(app)
    codec.setup(app)
    device.setup(app)

    error_response.setup(app)
    debug_api.setup(app)
    alias_api.setup(app)
    object_api.setup(app)
    profile_api.setup(app)
    system_api.setup(app)

    return app


async def response(request):
    retv = await request
    assert retv.status == 200
    return await retv.json()


async def test_do(app, client):
    command = dict(command='create_object', data={
        OBJECT_TYPE_KEY: 'OneWireTempSensor',
        PROFILE_LIST_KEY: [1, 2, 3],
        OBJECT_DATA_KEY: {
            'settings': {
                'address': 'FF',
                'offset': 20
            },
            'state': {
                'value': 1234,
                'connected': True
            }
        }
    })

    retv = await client.post('/_debug/do', json=command)
    assert retv.status == 200


async def test_create(app, client, object_args):
    # Create object
    retd = await response(client.post('/objects', json=object_args))
    assert retd[API_ID_KEY] == object_args[API_ID_KEY]

    # Conflict error: name already taken
    retv = await client.post('/objects', json=object_args)
    assert retv.status == 409

    object_args[API_ID_KEY] = 'other_obj'
    retd = await response(client.post('/objects', json=object_args))
    assert retd[API_ID_KEY] == 'other_obj'


async def test_create_performance(app, client, object_args):
    def custom(num):
        return {
            API_ID_KEY: f'id{num}',
            PROFILE_LIST_KEY: [1, 4, 7],
            API_TYPE_KEY: 'OneWireTempSensor',
            API_DATA_KEY: {
                'settings': {
                    'address': 'FF',
                    'offset': 20
                },
                'state': {
                    'value': 12345,
                    'connected': True
                }
            }
        }

    num_items = 50
    coros = [client.post('/objects', json=custom(i))for i in range(num_items)]
    responses = await asyncio.gather(*coros)
    assert [retv.status for retv in responses] == [200]*num_items

    retd = await response(client.get('/saved_objects'))
    assert len(retd) == num_items


async def test_read(app, client, object_args):
    retv = await client.get('/objects/testobj')
    assert retv.status == 500  # Object does not exist

    await client.post('/objects', json=object_args)

    retd = await response(client.get('/objects/testobj'))
    assert retd[API_ID_KEY] == 'testobj'


async def test_read_performance(app, client, object_args):
    await client.post('/objects', json=object_args)

    coros = [client.get('/objects/testobj') for _ in range(100)]
    responses = await asyncio.gather(*coros)
    assert [retv.status for retv in responses] == [200]*100


async def test_update(app, client, object_args):
    await client.post('/objects', json=object_args)
    assert await response(client.put('/objects/testobj', json=object_args))


async def test_delete(app, client, object_args):
    await client.post('/objects', json=object_args)

    retd = await response(client.delete('/objects/testobj'))
    assert retd[API_ID_KEY] == 'testobj'

    retv = await client.get('/objects/testobj')
    assert retv.status == 500


async def test_all(app, client, object_args):
    assert await response(client.get('/saved_objects')) == []

    await client.post('/objects', json=object_args)
    retd = await response(client.get('/saved_objects'))
    assert len(retd) == 1


async def test_active(app, client, object_args):
    retd = await response(client.get('/objects'))
    assert retd == []

    await client.post('/objects', json=object_args)
    retd = await response(client.get('/objects'))
    assert retd == []

    await client.post('/profiles', json=[1])

    retd = await response(client.get('/objects'))
    assert len(retd) == 1
    assert retd[0][API_ID_KEY] == object_args[API_ID_KEY]


async def test_system_read(app, client, object_args):
    # No system objects found
    # TODO(Bob): add preset system objects to simulator
    await response(client.get('/system/onewirebus'))


async def test_system_update(app, client, object_args):
    # No system objects found
    # TODO(Bob): add preset system objects to simulator
    await response(client.put('/system/onewirebus', json=object_args))


async def test_profiles(app, client):
    retd = await response(client.get('/profiles'))
    assert retd == []

    active = [1, 6, 7]
    retd = await response(client.post('/profiles', json=active))
    assert retd == active

    retd = await response(client.get('/profiles'))
    assert retd == active


@pytest.mark.parametrize('input_id', [
    'flabber',
    'FLABBER',
    'f',
    'a;ljfoihoewr*&(%&^&*%*&^(*&^(',
    'l1214235234231',
    'yes!'*50,
])
async def test_validate_service_id(input_id):
    alias_api.validate_service_id(input_id)


@pytest.mark.parametrize('input_id', [
    '1',
    '1adsjlfdsf',
    'pancakes[delicious]',
    '[',
    'f]abbergasted',
    '',
    'yes!'*51,
])
async def test_validate_service_id_error(input_id):
    with pytest.raises(ValueError):
        alias_api.validate_service_id(input_id)


async def test_alias_create(app, client):
    new_alias = dict(
        service_id='name',
        controller_id=456
    )
    retv = await client.post('/aliases', json=new_alias)
    assert retv.status == 200

    retv = await client.post('/aliases', json=new_alias)
    assert retv.status == 200


async def test_alias_update(app, client, object_args):
    await client.post('/objects', json=object_args)

    retv = await client.get('/objects/newname')
    assert retv.status == 500

    retv = await client.put('/aliases/testobj', json={'id': 'newname'})
    assert retv.status == 200

    retv = await client.get('/objects/newname')
    assert retv.status == 200
