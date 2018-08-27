"""
Tests brewblox_devcon_spark.api
"""

import asyncio

import pytest
from brewblox_service import scheduler

from brewblox_devcon_spark import (commander_sim, datastore, device,
                                   exceptions, status)
from brewblox_devcon_spark.api import (alias_api, debug_api, error_response,
                                       object_api, system_api)
from brewblox_devcon_spark.api.object_api import (API_DATA_KEY, API_ID_KEY,
                                                  API_TYPE_KEY,
                                                  OBJECT_DATA_KEY,
                                                  OBJECT_ID_KEY,
                                                  OBJECT_TYPE_KEY,
                                                  PROFILE_LIST_KEY)
from brewblox_devcon_spark.codec import codec

N_SYS_OBJ = len(datastore.SYS_OBJECTS)


@pytest.fixture
def object_args():
    return {
        API_ID_KEY: 'testobj',
        PROFILE_LIST_KEY: [0],
        API_TYPE_KEY: 'OneWireTempSensor',
        API_DATA_KEY: {
            'value': 12345,
            'connected': True,
            'offset': 20,
            'address': 'FF'
        }
    }


@pytest.fixture
async def app(app, loop):
    """App + controller routes"""
    status.setup(app)
    scheduler.setup(app)
    commander_sim.setup(app)
    datastore.setup(app)
    codec.setup(app)
    device.setup(app)

    error_response.setup(app)
    debug_api.setup(app)
    alias_api.setup(app)
    object_api.setup(app)
    system_api.setup(app)

    return app


@pytest.fixture
async def production_app(app, loop):
    app['config']['debug'] = False
    return app


async def response(request):
    retv = await request
    assert retv.status == 200
    return await retv.json()


async def test_do(app, client):
    command = {
        'command': 'create_object',
        'data': {
            OBJECT_ID_KEY: 0,
            OBJECT_TYPE_KEY: 'OneWireTempSensor',
            PROFILE_LIST_KEY: [1, 2, 3],
            OBJECT_DATA_KEY: {
                'value': 12345,
                'connected': True,
                'offset': 20,
                'address': 'FF'
            }
        }
    }

    await response(client.post('/_debug/do', json=command))

    error_command = {
        'command': 'create_object',
        'data': {}
    }

    retv = await client.post('/_debug/do', json=error_command)
    assert retv.status == 500
    retd = await retv.text()
    assert 'KeyError' in retd


async def test_production_do(production_app, client):
    error_command = {
        'command': 'create_object',
        'data': {}
    }

    retv = await client.post('/_debug/do', json=error_command)
    assert retv.status == 500


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


async def test_invalid_input(app, client, object_args):
    del object_args['profiles']
    retv = await client.post('/objects', json=object_args)
    assert retv.status == 400
    errtext = await retv.text()
    assert 'MissingInput' in errtext
    assert 'profiles' in errtext


async def test_create_performance(app, client, object_args):
    def custom(num):
        return {
            API_ID_KEY: f'id{num}',
            PROFILE_LIST_KEY: object_args[PROFILE_LIST_KEY],
            API_TYPE_KEY: object_args[API_TYPE_KEY],
            API_DATA_KEY: object_args[API_DATA_KEY]
        }

    num_items = 50
    coros = [client.post('/objects', json=custom(i))for i in range(num_items)]
    responses = await asyncio.gather(*coros)
    assert [retv.status for retv in responses] == [200]*num_items

    retd = await response(client.get('/objects'))
    assert len(retd) == num_items + N_SYS_OBJ


async def test_read(app, client, object_args):
    retv = await client.get('/objects/testobj')
    assert retv.status == 400  # Object does not exist

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
    assert retv.status == 400


async def test_all(app, client, object_args):
    retd = await response(client.get('/stored_objects'))
    assert len(retd) == N_SYS_OBJ

    await client.post('/objects', json=object_args)
    retd = await response(client.get('/stored_objects'))
    assert len(retd) == 1 + N_SYS_OBJ


async def test_clear(app, client, object_args):
    for i in range(5):
        object_args[API_ID_KEY] = f'id{i}'
        await client.post('/objects', json=object_args)

    assert len(await response(client.get('/objects'))) == 5 + N_SYS_OBJ
    await client.delete('/objects')
    assert len(await response(client.get('/objects'))) == N_SYS_OBJ


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
    'brackey><',
])
async def test_validate_service_id_error(input_id):
    with pytest.raises(exceptions.InvalidId):
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
    assert retv.status == 400

    retv = await client.put('/aliases/testobj', json={'id': 'newname'})
    assert retv.status == 200

    retv = await client.get('/objects/newname')
    assert retv.status == 200


async def test_profiles(app, client):
    profiles = await response(client.get('/system/profiles'))
    assert profiles == [0]  # Profiles initialize as [0]
    updated = await response(client.put('/system/profiles', json=[0, 1, 2]))
    assert updated == [0, 1, 2]
    assert updated == (await response(client.get('/system/profiles')))


async def test_inactive_objects(app, client, object_args):
    object_args[PROFILE_LIST_KEY] = [1]
    await client.post('/objects', json=object_args)

    retd = await response(client.get('/objects'))
    assert retd[-1] == {
        API_ID_KEY: object_args[API_ID_KEY],
        PROFILE_LIST_KEY: [1],
        API_TYPE_KEY: 'InactiveObject',
        API_DATA_KEY: {
            'actualType': object_args[API_TYPE_KEY]
        }
    }
