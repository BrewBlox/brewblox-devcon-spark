"""
Tests brewblox_devcon_spark.api
"""

import pytest
from brewblox_devcon_spark import api, device, commander
from asynctest import CoroutineMock


TESTED = api.__name__


@pytest.fixture
def object_args():
    return dict(
        type=6,
        obj=dict(
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
def commander_mock(mocker, loop):
    cmder = commander.SparkCommander(loop=loop)

    def echo(command):
        retval = command.decoded_request
        retval['command'] = command.name
        return retval

    cmder.write = CoroutineMock()
    cmder.do = CoroutineMock()
    cmder.execute = CoroutineMock()
    cmder.execute.side_effect = echo
    return cmder


@pytest.fixture
def controller_mock(mocker, commander_mock):
    controller = device.SparkController('sparky')
    controller._commander = commander_mock

    mocker.patch(device.__name__ + '.get_controller').return_value = controller
    return controller


@pytest.fixture
async def app(app, controller_mock):
    """App + controller routes"""
    api.setup(app)
    return app


async def test_write(app, client, commander_mock):
    commander_mock.write.return_value = 'reply'

    res = await client.post('/_debug/write', json=dict(command='text'))
    assert res.status == 200
    assert (await res.json()) == dict(written='reply')
    assert commander_mock.write.call_count == 1


async def test_do(app, client, commander_mock):
    command = dict(command='abracadabra', kwargs=dict(magic=True))
    retval = dict(response='ok')
    commander_mock.do.return_value = retval

    res = await client.post('/_debug/do', json=command)
    assert res.status == 200
    assert (await res.json()) == retval
    assert commander_mock.do.call_count == 1


async def test_create(app, client, object_args):
    res = await client.post('/objects', json=object_args)
    assert res.status == 200
    assert (await res.json())['command'] == 'CREATE_OBJECT'


async def test_read(app, client):
    res = await client.get('/objects/1-2-3')
    assert res.status == 200

    retval = await res.json()
    assert retval['command'] == 'READ_VALUE'
    assert retval['id'] == [1, 2, 3]


async def test_update(app, client, object_args):
    res = await client.put('/objects/1-2-3', json=object_args)
    assert res.status == 200
    retval = await res.json()
    assert retval['command'] == 'WRITE_VALUE'


async def test_delete(app, client):
    res = await client.delete('/objects/55-2')
    assert res.status == 200
    retval = await res.json()
    assert retval['command'] == 'DELETE_OBJECT'
    assert retval['id'] == [55, 2]


async def test_all(app, client):
    res = await client.get('/objects')
    assert res.status == 200
    retval = await res.json()
    assert retval['command'] == 'LIST_OBJECTS'


async def test_system_read(app, client):
    res = await client.get('/system/1-2-3')
    assert res.status == 200

    retval = await res.json()
    assert retval['command'] == 'READ_SYSTEM_VALUE'
    assert retval['id'] == [1, 2, 3]


async def test_system_update(app, client, object_args):
    res = await client.put('/system/1-2-3', json=object_args)
    assert res.status == 200
    retval = await res.json()
    assert retval['command'] == 'WRITE_SYSTEM_VALUE'


async def test_profile_create(app, client):
    res = await client.post('/profiles')
    assert res.status == 200

    retval = await res.json()
    assert retval['command'] == 'CREATE_PROFILE'


async def test_profile_delete(app, client):
    res = await client.delete('/profiles/1')
    assert res.status == 200

    retval = await res.json()
    assert retval['command'] == 'DELETE_PROFILE'


async def test_profile_activate(app, client):
    res = await client.post('/profiles/1')
    assert res.status == 200

    retval = await res.json()
    assert retval['command'] == 'ACTIVATE_PROFILE'


async def test_command_exception(app, client, commander_mock):
    commander_mock.execute.side_effect = RuntimeError('test error')

    res = await client.post('/profiles')
    assert res.status == 500

    retval = await res.json()
    assert retval['error'] == 'RuntimeError: test error'
