"""
Tests brewblox_devcon_spark.api
"""

import pytest

from brewblox_devcon_spark import api, commander_sim, datastore, device

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
def object_store():
    return datastore.MemoryDataStore()


@pytest.fixture
def system_store():
    return datastore.MemoryDataStore()


@pytest.fixture
def object_cache():
    return datastore.MemoryDataStore()


@pytest.fixture
def controller_mock(mocker, object_store, system_store, object_cache):
    controller = device.SparkController('sparky')

    controller._object_store = object_store
    controller._system_store = system_store
    controller._object_cache = object_cache

    mocker.patch(device.__name__ + '.get_controller').return_value = controller
    return controller


@pytest.fixture
async def app(app, controller_mock, object_store, system_store, loop):
    """App + controller routes"""
    api.setup(app)

    controller_mock._commander = commander_sim.SimulationCommander(loop)
    await controller_mock._commander.bind()

    await object_store.start(loop=loop)
    await object_store.insert(dict(service_id='testobj', controller_id=[1, 2, 3]))

    await system_store.start(loop=loop)
    await system_store.insert(dict(service_id='sysobj', controller_id=[3, 2, 1]))

    return app


async def test_do(app, client, object_args):
    command = dict(command='create_object', data=object_args)

    res = await client.post('/_debug/do', json=command)
    assert res.status == 200


async def test_create(app, client, object_args):
    res = await client.post('/objects', json=object_args)

    # Allowed to create a new object, but we don't get provided ID
    assert res.status == 200
    assert (await res.json())['id'] != object_args['id']

    object_args['id'] = 'other_obj'
    res = await client.post('/objects', json=object_args)
    assert res.status == 200


async def test_read(app, client):
    res = await client.get('/objects/testobj')
    assert res.status == 200

    retval = await res.json()
    assert retval['id'] == 'testobj'


async def test_update(app, client, object_args):
    res = await client.put('/objects/testobj', json=object_args)
    assert res.status == 200
    retval = await res.json()
    assert retval


async def test_delete(app, client):

    res = await client.delete('/objects/testobj')
    assert res.status == 200
    retval = await res.json()
    assert retval['id'] == 'testobj'


async def test_all(app, client):
    res = await client.get('/objects')
    assert res.status == 200
    retval = await res.json()
    assert retval


async def test_system_read(app, client):
    res = await client.get('/system/sysobj')
    assert res.status == 200

    retval = await res.json()
    assert retval['id'] == 'sysobj'


async def test_system_update(app, client, object_args):
    res = await client.put('/system/sysobj', json=object_args)
    assert res.status == 200


async def test_profile_create(app, client):
    res = await client.post('/profiles')
    assert res.status == 200


async def test_profile_delete(app, client):
    res = await client.delete('/profiles/1')
    assert res.status == 200

    retval = await res.json()
    assert retval


async def test_profile_activate(app, client):
    res = await client.post('/profiles/1')
    assert res.status == 200


async def test_profile_all(app, client):
    res = await client.get('/profiles')
    assert res.status == 200
    retval = await res.json()
    assert retval['profiles']


async def test_with_controller_id(app, client, object_args):
    object_args['object_id'] = [7, 8, 9]

    command = dict(command='write_value', data=object_args)
    res = await client.post('/_debug/do', json=command)
    assert res.status == 200

    # ID is parsed, but unknown, so a new ID is generated
    retval = await res.json()
    assert retval['object_id'] == '7-8-9'

    # We should be able to read it
    res = await client.get('/objects/7-8-9')
    assert res.status == 200


async def test_alias_create(app, client):
    new_alias = dict(
        service_id='name',
        controller_id=[4, 5, 6]
    )
    res = await client.post('/aliases', json=new_alias)
    assert res.status == 200

    res = await client.post('/aliases', json=new_alias)
    assert res.status == 500


async def test_alias_update(app, client):
    res = await client.get('/objects/newname')
    assert res.status == 500

    res = await client.put('/aliases/testobj', json={'id': 'newname'})
    assert res.status == 200

    res = await client.get('/objects/newname')
    assert res.status == 200
