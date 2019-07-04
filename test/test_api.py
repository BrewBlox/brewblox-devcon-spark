"""
Tests brewblox_devcon_spark.api
"""

import asyncio
from unittest.mock import ANY

import pytest
from asynctest import CoroutineMock
from brewblox_service import scheduler

from brewblox_devcon_spark import (commander_sim, datastore, device,
                                   exceptions, seeder, status)
from brewblox_devcon_spark.api import (alias_api, codec_api, debug_api,
                                       error_response, object_api, sse_api,
                                       system_api)
from brewblox_devcon_spark.api.object_api import (API_DATA_KEY, API_NID_KEY,
                                                  API_SID_KEY, API_TYPE_KEY,
                                                  GROUP_LIST_KEY,
                                                  OBJECT_DATA_KEY,
                                                  OBJECT_SID_KEY,
                                                  OBJECT_TYPE_KEY)
from brewblox_devcon_spark.codec import codec


def ret_ids(objects):
    return {obj[API_SID_KEY] for obj in objects}


@pytest.fixture
def object_args():
    return {
        API_SID_KEY: 'testobj',
        GROUP_LIST_KEY: [0],
        API_TYPE_KEY: 'TempSensorOneWire',
        API_DATA_KEY: {
            'value': 12345,
            'offset': 20,
            'address': 'FF'
        }
    }


def multi_objects(ids, args):
    return [{
        API_SID_KEY: id,
        GROUP_LIST_KEY: args[GROUP_LIST_KEY],
        API_TYPE_KEY: args[API_TYPE_KEY],
        API_DATA_KEY: args[API_DATA_KEY]
    } for id in ids]


@pytest.fixture
async def app(app, loop):
    """App + controller routes"""
    status.setup(app)
    scheduler.setup(app)
    commander_sim.setup(app)
    datastore.setup(app)
    codec.setup(app)
    seeder.setup(app)
    device.setup(app)

    error_response.setup(app)
    debug_api.setup(app)
    alias_api.setup(app)
    object_api.setup(app)
    system_api.setup(app)
    codec_api.setup(app)
    sse_api.setup(app)

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
            OBJECT_SID_KEY: 0,
            OBJECT_TYPE_KEY: 'TempSensorOneWire',
            GROUP_LIST_KEY: [1, 2, 3],
            OBJECT_DATA_KEY: {
                'value': 12345,
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
    assert retd[API_SID_KEY] == object_args[API_SID_KEY]

    # Conflict error: name already taken
    retv = await client.post('/objects', json=object_args)
    assert retv.status == 409

    object_args[API_SID_KEY] = 'other_obj'
    retd = await response(client.post('/objects', json=object_args))
    assert retd[API_SID_KEY] == 'other_obj'


async def test_invalid_input(app, client, object_args):
    del object_args['groups']
    retv = await client.post('/objects', json=object_args)
    assert retv.status == 400
    errtext = await retv.text()
    assert 'MissingInput' in errtext
    assert 'groups' in errtext


async def test_create_performance(app, client, object_args):
    num_items = 50
    ids = [f'id{num}' for num in range(num_items)]
    objs = multi_objects(ids, object_args)

    coros = [client.post('/objects', json=obj) for obj in objs]
    responses = await asyncio.gather(*coros)
    assert [retv.status for retv in responses] == [200]*num_items

    retd = await response(client.get('/objects'))
    assert set(ids).issubset(ret_ids(retd))


async def test_read(app, client, object_args):
    retv = await client.get('/objects/testobj')
    assert retv.status == 400  # Object does not exist

    await client.post('/objects', json=object_args)

    retd = await response(client.get('/objects/testobj'))
    assert retd[API_SID_KEY] == 'testobj'


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
    assert retd[API_SID_KEY] == 'testobj'

    retv = await client.get('/objects/testobj')
    assert retv.status == 400


async def test_nid_crud(app, client, object_args):
    created = await response(client.post('/objects', json=object_args))
    nid = created[API_NID_KEY]

    created[API_DATA_KEY]['value'] = 5
    await response(client.get(f'/objects/{nid}'))
    await response(client.put(f'/objects/{nid}', json=created))
    await response(client.delete(f'/objects/{nid}'))

    retv = await client.get('/objects/testobj')
    assert retv.status == 400


async def test_stored_objects(app, client, object_args):
    retd = await response(client.get('/stored_objects'))
    base_num = len(retd)

    await client.post('/objects', json=object_args)
    retd = await response(client.get('/stored_objects'))
    assert len(retd) == 1 + base_num

    retd = await response(client.get('/stored_objects/testobj'))
    assert retd[API_SID_KEY] == 'testobj'

    retv = await client.get('/stored_objects/flappy')
    assert retv.status == 400


async def test_clear(app, client, object_args):
    n_sys_obj = len(await response(client.get('/objects')))

    for i in range(5):
        object_args[API_SID_KEY] = f'id{i}'
        await client.post('/objects', json=object_args)

    assert len(await response(client.get('/objects'))) == 5 + n_sys_obj
    await client.delete('/objects')
    assert len(await response(client.get('/objects'))) == n_sys_obj


async def test_unused(app, client, object_args):
    new_alias = dict(
        sid='unused',
        nid=456
    )
    await client.post('/aliases', json=new_alias)
    await client.post('/objects', json=object_args)
    retv = await response(client.delete('/unused_names'))
    assert 'unused' in retv
    assert object_args[API_SID_KEY] not in retv


@pytest.mark.parametrize('sid', [
    'flabber',
    'FLABBER',
    'f(1)',
    'l12142|35234231',
    'word'*50,
])
async def test_validate_sid(sid):
    alias_api.validate_sid(sid)


@pytest.mark.parametrize('sid', [
    '1',
    '1adsjlfdsf',
    'pancakes[delicious]',
    '[',
    'f]abbergasted',
    '',
    'word'*51,
    'brackey><',
    'ActiveGroups',
    'SparkPins',
    'a;ljfoihoewr*&(%&^&*%*&^(*&^(',
])
async def test_validate_sid_error(sid):
    with pytest.raises(exceptions.InvalidId):
        alias_api.validate_sid(sid)


async def test_alias_create(app, client):
    new_alias = dict(
        sid='name',
        nid=456
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


async def test_alias_delete(app, client, object_args):
    await client.post('/objects', json=object_args)

    retv = await client.delete('/aliases/testobj')
    assert retv.status == 200

    retv = await client.get('/objects/testobj')
    assert retv.status == 400


async def test_ping(app, client):
    await response(client.get('/system/ping'))


async def test_groups(app, client):
    groups = await response(client.get('/system/groups'))
    assert groups == [0, device.SYSTEM_GROUP]  # Initialized value
    updated = await response(client.put('/system/groups', json=[0, 1, 2]))
    assert updated == [0, 1, 2]
    assert updated == (await response(client.get('/system/groups')))


async def test_inactive_objects(app, client, object_args):
    object_args[GROUP_LIST_KEY] = [1]
    await client.post('/objects', json=object_args)

    retd = await response(client.get('/objects'))
    assert retd[-1] == {
        API_SID_KEY: object_args[API_SID_KEY],
        API_NID_KEY: ANY,
        GROUP_LIST_KEY: [1],
        API_TYPE_KEY: 'InactiveObject',
        API_DATA_KEY: {
            'actualType': object_args[API_TYPE_KEY]
        }
    }


async def test_codec_api(app, client, object_args):
    degC_offset = object_args[API_DATA_KEY]['offset']
    degF_offset = degC_offset * (9/5)  # delta_degC to delta_degF
    await client.post('/objects', json=object_args)

    default_units = await response(client.get('/codec/units'))
    assert {'Temp', 'Time', 'LongTime'} == default_units.keys()

    alternative_units = await response(client.get('/codec/unit_alternatives'))
    assert alternative_units.keys() == default_units.keys()

    # offset is a delta_degC value
    # We'd expect to get the same value in delta_celsius as in degK

    await client.put('/codec/units', json={'Temp': 'degF'})
    retd = await response(client.get(f'/objects/{object_args[API_SID_KEY]}'))
    assert retd[API_DATA_KEY]['offset[delta_degF]'] == pytest.approx(degF_offset, 0.1)

    await client.put('/codec/units', json={'Temp': 'degK'})
    retd = await response(client.get(f'/objects/{object_args[API_SID_KEY]}'))
    assert retd[API_DATA_KEY]['offset[degK]'] == pytest.approx(degC_offset, 0.1)

    await client.put('/codec/units', json={})
    retd = await response(client.get(f'/objects/{object_args[API_SID_KEY]}'))
    assert retd[API_DATA_KEY]['offset[delta_degC]'] == pytest.approx(degC_offset, 0.1)

    retd = await response(client.get('/codec/compatible_types'))
    assert 'TempSensorOneWire' in retd['TempSensorInterface']


async def test_list_compatible(app, client, object_args):
    resp = await response(client.get('/compatible_objects', params={'interface': 'BalancerInterface'}))
    assert all([isinstance(id, str) for id in resp])


async def test_discover_objects(app, client):
    resp = await response(client.get('/discover_objects'))
    # Commander sim always returns the groups object
    assert resp == ['DisplaySettings']


async def test_export_objects(app, client, object_args):
    retd = await response(client.get('/export_objects'))
    base_num = len(retd['blocks'])

    await client.post('/objects', json=object_args)
    retd = await response(client.get('/export_objects'))
    assert len(retd['blocks']) == 1 + base_num


async def test_import_objects(app, client, spark_blocks):
    # reverse the set, to ensure some blocks are written with invalid references
    data = {
        'store': [{'keys': [block[API_SID_KEY], block[API_NID_KEY]], 'data': dict()} for block in spark_blocks],
        'blocks': spark_blocks[::-1],
    }
    resp = await response(client.post('/import_objects', json=data))
    assert resp == []

    resp = await response(client.get('/objects'))
    ids = ret_ids(spark_blocks)
    resp_ids = ret_ids(resp)
    assert set(ids).issubset(resp_ids)
    assert 'ActiveGroups' in resp_ids

    # Add an unused store alias
    data['store'].append({'keys': ['TROLOLOL', 9999], 'data': dict()})

    # Add renamed type to store data
    data['store'].append({'keys': ['renamed_wifi', datastore.WIFI_SETTINGS_NID], 'data': dict()})

    # Add a Block that will fail to be created, and should be skipped
    data['blocks'].append({
        API_SID_KEY: 'derpface',
        API_NID_KEY: 500,
        GROUP_LIST_KEY: [0],
        API_TYPE_KEY: 'INVALID',
        API_DATA_KEY: {}
    })

    retv = await response(client.post('/import_objects', json=data))
    assert len(retv) == 2
    assert 'derpface' in retv[0]
    assert 'TROLOLOL' in retv[1]

    resp = await response(client.get('/objects'))
    resp_ids = ret_ids(resp)
    assert 'renamed_wifi' in resp_ids
    assert 'derpface' not in resp_ids


async def test_logged_objects(app, client):
    args = {
        API_SID_KEY: 'edgey',
        GROUP_LIST_KEY: [0],
        API_TYPE_KEY: 'EdgeCase',
        API_DATA_KEY: {
            'logged': 12345,
            'unLogged': 54321,
        }
    }

    await client.post('/objects', json=args)
    listed = await response(client.get('/objects'))
    logged = await response(client.get('/logged_objects'))

    # list_objects returns everything
    obj = listed[-1]
    assert args[API_SID_KEY] == obj[API_SID_KEY]
    obj_data = obj[API_DATA_KEY]
    assert obj_data is not None
    assert 'logged' in obj_data
    assert 'unLogged' in obj_data

    # log_objects strips all keys that are not explicitly marked as logged
    obj = logged[-1]
    assert args[API_SID_KEY] == obj[API_SID_KEY]
    obj_data = obj[API_DATA_KEY]
    assert obj_data is not None
    assert 'logged' in obj_data
    assert 'unLogged' not in obj_data


async def test_system_status(app, client):
    resp = await response(client.get('/system/status'))
    assert resp == {
        'connect': True,
        'handshake': True,
        'synchronize': True,
        'compatible': True,
        'latest': True,
        'info': ANY,
    }
    await status.get_status(app).on_disconnect()
    await asyncio.sleep(0.01)
    resp = await response(client.get('/system/status'))
    assert resp == {
        'connect': False,
        'handshake': False,
        'synchronize': False,
        'compatible': True,
        'latest': True,
        'info': [],
    }


async def test_system_flash(app, client, mocker):
    sys_api = system_api.__name__
    mocker.patch(sys_api + '.REBOOT_WINDOW_S', 0.001)
    sender = mocker.patch(sys_api + '.ymodem.FileSender')
    transfer_mock = CoroutineMock()
    sender.return_value.transfer = transfer_mock

    await response(client.post('/system/flash'))
