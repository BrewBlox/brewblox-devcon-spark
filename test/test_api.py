"""
Tests brewblox_devcon_spark.api
"""

import asyncio

import pytest
from brewblox_service import scheduler
from brewblox_service.testing import response
from mock import ANY, AsyncMock

from brewblox_devcon_spark import (commander_sim, const, datastore, device,
                                   exceptions, service_status, synchronization,
                                   ymodem)
from brewblox_devcon_spark.api import (blocks_api, debug_api, error_response,
                                       settings_api, system_api)
from brewblox_devcon_spark.codec import codec, unit_conversion


class DummmyError(BaseException):
    pass


def ret_ids(objects):
    return {obj['id'] for obj in objects}


@pytest.fixture
def block_args():
    return {
        'id': 'testobj',
        'groups': [0],
        'type': 'TempSensorOneWire',
        'data': {
            'value': 12345,
            'offset': 20,
            'address': 'FF'
        }
    }


def repeated_blocks(ids, args):
    return [{
        'id': id,
        'groups': args['groups'],
        'type': args['type'],
        'data': args['data']
    } for id in ids]


@pytest.fixture
async def app(app, loop):
    """App + controller routes"""
    service_status.setup(app)
    scheduler.setup(app)
    commander_sim.setup(app)
    datastore.setup(app)
    unit_conversion.setup(app)
    codec.setup(app)
    synchronization.setup(app)
    device.setup(app)

    error_response.setup(app)
    debug_api.setup(app)
    blocks_api.setup(app)
    system_api.setup(app)
    settings_api.setup(app)

    return app


@pytest.fixture
async def production_app(app, loop):
    app['config']['debug'] = False
    return app


async def test_do(app, client):
    command = {
        'command': 'create_object',
        'data': {
            'nid': 0,
            'type': 'TempSensorOneWire',
            'groups': [1, 2, 3],
            'data': {
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

    retv = await response(client.post('/_debug/do', json=error_command), 500)
    assert 'KeyError' in retv['error']


async def test_production_do(production_app, client):
    error_command = {
        'command': 'create_object',
        'data': {}
    }

    await response(client.post('/_debug/do', json=error_command), 500)


async def test_create(app, client, block_args):
    # Create object
    retd = await response(client.post('/blocks/create', json=block_args), 201)
    assert retd['id'] == block_args['id']

    # Conflict error: name already taken
    await response(client.post('/blocks/create', json=block_args), 409)

    block_args['id'] = 'other_obj'
    retd = await response(client.post('/blocks/create', json=block_args), 201)
    assert retd['id'] == 'other_obj'


async def test_invalid_input(app, client, block_args):
    del block_args['groups']
    retv = await response(client.post('/blocks/create', json=block_args), 422)
    assert 'groups' in retv


async def test_create_performance(app, client, block_args):
    num_items = 50
    ids = [f'id{num}' for num in range(num_items)]
    blocks = repeated_blocks(ids, block_args)

    await asyncio.gather(*(response(client.post('/blocks/create', json=block), 201)
                           for block in blocks))

    retd = await response(client.post('/blocks/all/read'))
    assert set(ids).issubset(ret_ids(retd))


async def test_read(app, client, block_args):
    await response(client.post('/blocks/read', json={'id': 'testobj'}), 400)  # Object does not exist
    await response(client.post('/blocks/create', json=block_args), 201)

    retd = await response(client.post('/blocks/read', json={'id': 'testobj'}))
    assert retd['id'] == 'testobj'


async def test_read_performance(app, client, block_args):
    await response(client.post('/blocks/create', json=block_args), 201)
    await asyncio.gather(*(response(client.post('/blocks/read', json={'id': 'testobj'})) for _ in range(100)))


async def test_read_logged(app, client, block_args):
    await response(client.post('/blocks/create', json=block_args), 201)

    retd = await response(client.post('/blocks/read/logged', json={'id': 'testobj'}))
    assert retd['id'] == 'testobj'
    assert 'address' not in retd['data']  # address is not a logged field


async def test_update(app, client, block_args):
    await response(client.post('/blocks/create', json=block_args), 201)
    assert await response(client.post('/blocks/write', json=block_args))


async def test_delete(app, client, block_args):
    await response(client.post('/blocks/create', json=block_args), 201)

    retd = await response(client.post('/blocks/delete', json={'id': 'testobj'}))
    assert retd['id'] == 'testobj'

    await response(client.post('/blocks/read', json={'id': 'testobj'}), 400)


async def test_nid_crud(app, client, block_args):
    created = await response(client.post('/blocks/create', json=block_args), 201)
    nid = created['nid']

    created['data']['value'] = 5
    await response(client.post('/blocks/read', json={'nid': nid}))
    await response(client.post('/blocks/write', json=created))
    await response(client.post('/blocks/delete', json={'nid': nid}))

    await response(client.post('/blocks/read', json={'nid': nid}), 500)


async def test_stored_blocks(app, client, block_args):
    retd = await response(client.post('/blocks/all/read/stored'))
    base_num = len(retd)

    await response(client.post('/blocks/create', json=block_args), 201)
    retd = await response(client.post('/blocks/all/read/stored'))
    assert len(retd) == 1 + base_num

    retd = await response(client.post('/blocks/read/stored', json={'id': 'testobj'}))
    assert retd['id'] == 'testobj'

    await response(client.post('/blocks/read/stored', json={'id': 'flappy'}), 400)


async def test_delete_all(app, client, block_args):
    n_sys_obj = len(await response(client.post('/blocks/all/read')))

    for i in range(5):
        block_args['id'] = f'id{i}'
        await response(client.post('/blocks/create', json=block_args), 201)

    assert len(await response(client.post('/blocks/all/read'))) == 5 + n_sys_obj
    await response(client.post('/blocks/all/delete'))
    assert len(await response(client.post('/blocks/all/read'))) == n_sys_obj


async def test_cleanup(app, client, block_args):
    store = datastore.get_block_store(app)
    await response(client.post('/blocks/create', json=block_args), 201)
    store['unused', 456] = {}
    retv = await response(client.post('/blocks/cleanup'))
    assert {'id': 'unused', 'nid': 456} in retv
    assert not [v for v in retv if v['id'] == 'testobj']


@pytest.mark.parametrize('sid', [
    'flabber',
    'FLABBER',
    'f(1)',
    'l12142|35234231',
    'word'*50,
])
async def test_validate_sid(sid):
    blocks_api.validate_sid(sid)


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
        blocks_api.validate_sid(sid)


async def test_rename(app, client, block_args):
    await response(client.post('/blocks/create', json=block_args), 201)
    existing = block_args['id']
    desired = 'newname'

    await response(client.post('/blocks/read', json={'id': desired}), 400)
    await response(client.post('/blocks/rename', json={
        'existing': existing,
        'desired': desired
    }))
    await response(client.post('/blocks/read', json={'id': desired}))


async def test_ping(app, client):
    await response(client.post('/system/ping'))


async def test_settings_api(app, client, block_args):
    degC_offset = block_args['data']['offset']
    degF_offset = degC_offset * (9/5)  # delta_degC to delta_degF
    await response(client.post('/blocks/create', json=block_args), 201)

    default_units = await response(client.get('/settings/units'))
    assert {'Temp'} == default_units.keys()

    # offset is a delta_degC value
    # We'd expect to get the same value in delta_celsius as in degK

    await response(client.put('/settings/units', json={'Temp': 'degF'}))
    retd = await response(client.post('/blocks/read', json={'id': block_args['id']}))
    assert retd['data']['offset']['value'] == pytest.approx(degF_offset, 0.1)
    assert retd['data']['offset']['unit'] == 'delta_degF'

    await response(client.put('/settings/units', json={'Temp': 'degC'}))
    retd = await response(client.post('/blocks/read', json={'id': block_args['id']}))
    assert retd['data']['offset']['value'] == pytest.approx(degC_offset, 0.1)

    retd = await response(client.get('/settings/autoconnecting'))
    assert retd == {'enabled': True}

    retd = await response(client.put('/settings/autoconnecting', json={'enabled': False}))
    assert retd == {'enabled': False}
    retd = await response(client.get('/settings/autoconnecting'))
    assert retd == {'enabled': False}


async def test_compatible(app, client, block_args):
    resp = await response(client.post('/blocks/compatible', json={'interface': 'BalancerInterface'}))
    print(resp)
    assert all([isinstance(v['id'], str) for v in resp])


async def test_discover(app, client):
    resp = await response(client.post('/blocks/discover'))
    # Commander sim always returns the groups object
    print(resp)
    assert resp[0]['id'] == 'DisplaySettings'


async def test_validate(app, client, block_args):
    validate_args = {
        'type': block_args['type'],
        'data': block_args['data'],
    }
    await response(client.post('/blocks/validate', json=validate_args))

    invalid_data_obj = {
        'type': block_args['type'],
        'data': {**block_args['data'], 'invalid': True}
    }
    await response(client.post('/blocks/validate', json=invalid_data_obj), 400)

    invalid_link_obj = {
        'type': 'SetpointSensorPair',
        'data': {
            'sensorId<>': 'Santa',
            'setting': 0,
            'value': 0,
            'settingEnabled': True,
            'filter': 'FILT_15s',
            'filterThreshold': 2
        }
    }
    await response(client.post('/blocks/validate', json=invalid_link_obj), 400)


async def test_backup_save(app, client, block_args):
    retd = await response(client.post('/blocks/backup/save'))
    base_num = len(retd['blocks'])

    await response(client.post('/blocks/create', json=block_args), 201)
    retd = await response(client.post('/blocks/backup/save'))
    assert len(retd['blocks']) == 1 + base_num


async def test_backup_load(app, client, spark_blocks):
    # reverse the set, to ensure some blocks are written with invalid references
    data = {
        'store': [{'keys': [block['id'], block['nid']], 'data': dict()} for block in spark_blocks],
        'blocks': spark_blocks[::-1],
    }
    resp = await response(client.post('/blocks/backup/load', json=data))
    assert resp == {'messages': []}

    resp = await response(client.post('/blocks/all/read'))
    ids = ret_ids(spark_blocks)
    resp_ids = ret_ids(resp)
    assert set(ids).issubset(resp_ids)
    assert 'ActiveGroups' in resp_ids

    # Add an unused store alias
    data['store'].append({'keys': ['TROLOLOL', 9999], 'data': dict()})

    # Add renamed type to store data
    data['store'].append({'keys': ['renamed_wifi', const.WIFI_SETTINGS_NID], 'data': dict()})

    # Add a Block that will fail to be created, and should be skipped
    data['blocks'].append({
        'id': 'derpface',
        'nid': 500,
        'groups': [0],
        'type': 'INVALID',
        'data': {}
    })

    resp = await response(client.post('/blocks/backup/load', json=data))
    resp = resp['messages']
    assert len(resp) == 2
    assert 'derpface' in resp[0]
    assert 'TROLOLOL' in resp[1]

    resp = await response(client.post('/blocks/all/read'))
    resp_ids = ret_ids(resp)
    assert 'renamed_wifi' in resp_ids
    assert 'derpface' not in resp_ids


async def test_read_all_logged(app, client):
    args = {
        'id': 'edgey',
        'groups': [0],
        'type': 'EdgeCase',
        'data': {
            'logged': 12345,
            'unLogged': 54321,
        }
    }

    await response(client.post('/blocks/create', json=args), 201)
    all = await response(client.post('/blocks/all/read'))
    logged = await response(client.post('/blocks/all/read/logged'))

    # list_objects returns everything
    obj = all[-1]
    assert args['id'] == obj['id']
    obj_data = obj['data']
    assert obj_data is not None
    assert 'logged' in obj_data
    assert 'unLogged' in obj_data

    # log_objects strips all keys that are not explicitly marked as logged
    obj = logged[-1]
    assert args['id'] == obj['id']
    obj_data = obj['data']
    assert obj_data is not None
    assert 'logged' in obj_data
    assert 'unLogged' not in obj_data


async def test_system_status(app, client):
    resp = await response(client.get('/system/status'))

    fw_info = {
        'firmware_version': ANY,
        'proto_version': ANY,
        'firmware_date': ANY,
        'proto_date': ANY,
        'device_id': ANY,
    }

    assert resp == {
        'device_address': 'simulation:1234',
        'connection_kind': 'wifi',

        'service_info': {
            **fw_info,
            'name': 'test_app',
        },
        'device_info': {
            **fw_info,
            'system_version': ANY,
            'platform': ANY,
            'reset_reason': ANY,
        },
        'handshake_info': {
            'is_compatible_firmware': True,
            'is_latest_firmware': True,
            'is_valid_device_id': True,
        },
        'is_autoconnecting': True,
        'is_connected': True,
        'is_acknowledged': True,
        'is_synchronized': True,
    }

    service_status.set_disconnected(app)
    await asyncio.sleep(0.01)
    resp = await response(client.get('/system/status'))
    assert resp['is_synchronized'] is False
    assert resp['is_connected'] is False
    assert resp['device_info'] is None


async def test_system_flash(app, client, mocker):
    sys_api = system_api.__name__

    mocker.patch(sys_api + '.CONNECT_INTERVAL_S', 0.001)
    mocker.patch(sys_api + '.shutdown_soon', AsyncMock())
    mocker.patch(sys_api + '.mqtt.publish', AsyncMock())

    m_conn = mocker.patch(sys_api + '.ymodem.connect', AsyncMock())
    m_conn.return_value = AsyncMock(ymodem.Connection)

    m_sender = mocker.patch(sys_api + '.ymodem.FileSender')
    m_sender.return_value.transfer = AsyncMock()

    await response(client.post('/system/flash'))
    m_sender.return_value.transfer.assert_awaited()
    system_api.shutdown_soon.assert_awaited()


async def test_system_resets(app, client, mocker):
    sys_api = system_api.__name__
    mocker.patch(sys_api + '.shutdown_soon', AsyncMock())

    await response(client.post('/system/reboot/service'))
    system_api.shutdown_soon.assert_awaited()

    await response(client.post('/system/reboot/controller'))
    await response(client.post('/system/factory_reset'))
