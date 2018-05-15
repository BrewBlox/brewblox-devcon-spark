"""
Tests brewblox_devcon_spark.api
"""

import os

import pytest

from brewblox_devcon_spark import api, device, commander_sim, datastore

TESTED = api.__name__


@pytest.fixture
def object_args():
    return dict(
        id='testobj',
        type=6,
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

    commander_sim.setup(app)
    datastore.setup(app)
    device.setup(app)
    api.setup(app)

    return app


async def test_do(app, client, object_args):
    command = dict(command='create_object', data=object_args)

    res = await client.post('/_debug/do', json=command)
    assert res.status == 200


async def test_create(app, client, object_args):
    # Create object
    res = await client.post('/objects', json=object_args)
    assert res.status == 200
    assert (await res.json())['id'] == object_args['id']

    # Allowed to recreate, but we don't get provided ID
    res = await client.post('/objects', json=object_args)
    assert res.status == 200
    assert (await res.json())['id'] != object_args['id']

    object_args['id'] = 'other_obj'
    res = await client.post('/objects', json=object_args)
    assert res.status == 200
    assert (await res.json())['id'] == 'other_obj'


async def test_create_spam(app, client, object_args):
    for i in range(150):
        res = await client.post('/objects', json=object_args)
        assert res.status == 200


async def test_read(app, client, object_args):
    res = await client.get('/objects/testobj')
    assert res.status == 500  # Object does not exist

    await client.post('/objects', json=object_args)

    res = await client.get('/objects/testobj')
    assert res.status == 200

    retval = await res.json()
    assert retval['id'] == 'testobj'


async def test_update(app, client, object_args):
    await client.post('/objects', json=object_args)
    res = await client.put('/objects/testobj', json=object_args)
    assert res.status == 200
    retval = await res.json()
    assert retval


async def test_delete(app, client, object_args):
    await client.post('/objects', json=object_args)

    res = await client.delete('/objects/testobj')
    assert res.status == 200
    retval = await res.json()
    assert retval['id'] == 'testobj'

    res = await client.get('/objects/testobj')
    assert res.status == 500


async def test_all(app, client, object_args):
    res = await client.get('/objects')
    assert res.status == 200
    retval = await res.json()
    assert retval == []

    await client.post('/objects', json=object_args)
    res = await client.get('/objects')
    assert res.status == 200
    retval = await res.json()
    assert len(retval) == 1


async def test_all_data(app, client, object_args):
    res = await client.get('/data')
    assert res.status == 200
    retval = await res.json()
    assert retval == {}

    await client.post('/objects', json=object_args)
    res = await client.get('/data')
    assert res.status == 200
    retval = await res.json()
    assert len(retval) == 1
    assert retval[object_args['id']]


async def test_system_read(app, client, object_args):
    # No system objects found
    # TODO(Bob): add preset system objects to simulator
    res = await client.get('/system/onewirebus')
    assert res.status == 200


async def test_system_update(app, client, object_args):
    # No system objects found
    # TODO(Bob): add preset system objects to simulator
    res = await client.put('/system/onewirebus', json=object_args)
    assert res.status == 200


async def test_profile_create(app, client):
    res = await client.post('/profiles')
    assert res.status == 200
    retval = await res.json()
    assert retval['id']
    second = await (await client.post('/profiles')).json()
    assert second['id'] != retval['id']


async def test_profile_delete(app, client):
    res = await client.delete('/profiles/1')
    assert res.status == 200

    retval = await res.json()
    assert retval


async def test_profile_activate(app, client):
    res = await client.post('/profiles/1')
    assert res.status == 500  # profile doesn't exist

    created = await (await client.post('/profiles')).json()
    res = await client.post(f'/profiles/{created["id"]}')
    assert res.status == 200


async def test_profile_all(app, client):
    res = await client.get('/profiles')
    assert res.status == 200
    retval = await res.json()
    assert retval['profiles'] == []

    await client.post('/profiles')
    await client.post('/profiles')

    retval = await (await client.get('/profiles')).json()
    assert len(retval['profiles']) == 2


async def test_alias_create(app, client):
    new_alias = dict(
        service_id='name',
        controller_id=[4, 5, 6]
    )
    res = await client.post('/aliases', json=new_alias)
    assert res.status == 200

    res = await client.post('/aliases', json=new_alias)
    assert res.status == 500


async def test_alias_update(app, client, object_args):
    await client.post('/objects', json=object_args)

    res = await client.get('/objects/newname')
    assert res.status == 500

    res = await client.put('/aliases/testobj', json={'id': 'newname'})
    assert res.status == 200

    res = await client.get('/objects/newname')
    assert res.status == 200
