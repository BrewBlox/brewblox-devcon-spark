"""
Tests brewblox_devcon_spark.api
"""

import asyncio
import os

import pytest
from brewblox_service import scheduler

from brewblox_codec_spark import codec
from brewblox_devcon_spark import commander_sim, datastore, device
from brewblox_devcon_spark.api import (alias_api, conflict_api, debug_api,
                                       error_response, object_api, profile_api,
                                       system_api)


@pytest.fixture
def object_args():
    return dict(
        id='testobj',
        profiles=[1, 4, 7],
        type='OneWireTempSensor',
        data=dict(
            settings=dict(
                address='FF',
                offset=20
            ),
            state=dict(
                value=12345,
                connected=True
            )
        )
    )


@pytest.fixture
def database_test_file():
    def remove(f):
        try:
            os.remove(f)
        except FileNotFoundError:
            pass

    f = 'api_test_file.json'
    remove(f)
    yield f
    remove(f)


@pytest.fixture
async def app(app, database_test_file, loop):
    """App + controller routes"""
    app['config']['database'] = database_test_file

    scheduler.setup(app)
    commander_sim.setup(app)
    datastore.setup(app)
    codec.setup(app)
    device.setup(app)

    error_response.setup(app)
    debug_api.setup(app)
    alias_api.setup(app)
    conflict_api.setup(app)
    object_api.setup(app)
    profile_api.setup(app)
    system_api.setup(app)

    return app


async def test_do(app, client):
    command = dict(command='create_object', data={
        'object_type': 'OneWireTempSensor',
        'profiles': [1, 2, 3],
        'object_data': {
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
    retv = await client.post('/objects', json=object_args)
    assert retv.status == 200
    assert (await retv.json())['id'] == object_args['id']

    # Allowed to recreate, but we don't get provided ID
    retv = await client.post('/objects', json=object_args)
    assert retv.status == 200
    assert (await retv.json())['id'] != object_args['id']

    object_args['id'] = 'other_obj'
    retv = await client.post('/objects', json=object_args)
    assert retv.status == 200
    assert (await retv.json())['id'] == 'other_obj'


async def test_create_performance(app, client, object_args):
    num_items = 50
    coros = [client.post('/objects', json=object_args) for _ in range(num_items)]
    responses = await asyncio.gather(*coros)
    assert [retv.status for retv in responses] == [200]*num_items

    retv = await client.get('/saved')
    assert retv.status == 200
    retd = await retv.json()
    assert len(retd) == num_items


async def test_read(app, client, object_args):
    retv = await client.get('/objects/testobj')
    assert retv.status == 500  # Object does not exist

    await client.post('/objects', json=object_args)

    retv = await client.get('/objects/testobj')
    assert retv.status == 200

    retd = await retv.json()
    assert retd['id'] == 'testobj'


async def test_read_performance(app, client, object_args):
    await client.post('/objects', json=object_args)

    coros = [client.get('/objects/testobj') for _ in range(100)]
    responses = await asyncio.gather(*coros)
    assert [retv.status for retv in responses] == [200]*100


async def test_update(app, client, object_args):
    await client.post('/objects', json=object_args)
    retv = await client.put('/objects/testobj', json=object_args)
    assert retv.status == 200
    retd = await retv.json()
    assert retd


async def test_delete(app, client, object_args):
    await client.post('/objects', json=object_args)

    retv = await client.delete('/objects/testobj')
    assert retv.status == 200
    retd = await retv.json()
    assert retd['id'] == 'testobj'

    retv = await client.get('/objects/testobj')
    assert retv.status == 500


async def test_all(app, client, object_args):
    retv = await client.get('/saved')
    assert retv.status == 200
    retd = await retv.json()
    assert retd == []

    await client.post('/objects', json=object_args)
    retv = await client.get('/saved')
    assert retv.status == 200
    retd = await retv.json()
    assert len(retd) == 1


async def test_active(app, client, object_args):
    retv = await client.get('/objects')
    assert retv.status == 200
    retd = await retv.json()
    assert retd == []

    await client.post('/objects', json=object_args)
    retv = await client.get('/objects')
    assert retv.status == 200
    retd = await retv.json()
    assert retd == []

    await client.post('/profiles', json=[1])

    retv = await client.get('/objects')
    retd = await retv.json()
    assert len(retd) == 1
    assert retd[0]['id'] == object_args['id']


async def test_system_read(app, client, object_args):
    # No system objects found
    # TODO(Bob): add pretvet system objects to simulator
    retv = await client.get('/system/onewirebus')
    assert retv.status == 200


async def test_system_update(app, client, object_args):
    # No system objects found
    # TODO(Bob): add pretvet system objects to simulator
    retv = await client.put('/system/onewirebus', json=object_args)
    assert retv.status == 200


async def test_profiles(app, client):
    retv = await client.get('/profiles')
    assert retv.status == 200
    retd = await retv.json()
    assert retd == []

    active = [1, 6, 7]
    retv = await client.post('/profiles', json=active)
    assert retv.status == 200
    retd = await retv.json()
    assert retd == active

    retv = await client.get('/profiles')
    assert retv.status == 200
    retd = await retv.json()
    assert retd == active


async def test_alias_create(app, client):
    new_alias = dict(
        service_id='name',
        controller_id=456
    )
    retv = await client.post('/aliases', json=new_alias)
    assert retv.status == 200

    retv = await client.post('/aliases', json=new_alias)
    assert retv.status == 409


async def test_alias_update(app, client, object_args):
    await client.post('/objects', json=object_args)

    retv = await client.get('/objects/newname')
    assert retv.status == 500

    retv = await client.put('/aliases/testobj', json={'id': 'newname'})
    assert retv.status == 200

    retv = await client.get('/objects/newname')
    assert retv.status == 200


async def test_conflict_all(app, client):
    objects = [
        {'service_id': 'sid', 'controller_id': 8},
        {'service_id': 'sid', 'controller_id': 9}
    ]

    store = datastore.get_object_store(app)
    await store.insert_multiple(objects)

    retv = await client.get('/conflicts')
    assert retv.status == 200
    assert (await retv.json()) == dict()

    retv = await client.get('/objects/sid')
    assert retv.status == 428

    retv = await client.get('/conflicts')
    assert retv.status == 200
    assert (await retv.json()) == {
        'service_id': {
            'sid': objects
        }
    }


async def test_conflict_resolve(app, client, object_args):
    store = datastore.get_object_store(app)
    argid = object_args['id']

    await client.post('/objects', json=object_args)
    await store.insert({'service_id': argid, 'dummy': True})

    retv = await client.get('/objects/' + argid)
    assert retv.status == 428

    retv = await client.get('/conflicts')
    objects = (await retv.json())['service_id'][argid]
    assert len(objects) == 2

    # Pick the one that's not the dummy
    real = next(o for o in objects if 'dummy' not in o)

    retv = await client.post('/conflicts', json={'id_key': 'service_id', 'data': real})
    assert retv.status == 200

    retv = await client.get('/objects/' + argid)
    assert retv.status == 200
