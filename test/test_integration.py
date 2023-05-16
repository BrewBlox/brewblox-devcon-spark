"""
Integration tests: API calls against the firmware simulator.
"""

import asyncio
from shutil import rmtree
from unittest.mock import ANY, AsyncMock

import pytest
from brewblox_service import scheduler
from brewblox_service.testing import find_free_port, response

from brewblox_devcon_spark import (backup_storage, block_store, codec,
                                   commander, connection, const, controller,
                                   global_store, service_status, service_store,
                                   synchronization)
from brewblox_devcon_spark.__main__ import parse_ini
from brewblox_devcon_spark.api import (backup_api, blocks_api, debug_api,
                                       error_response, settings_api,
                                       system_api)
from brewblox_devcon_spark.connection import stream_connection
from brewblox_devcon_spark.models import (DecodedPayload, EncodedPayload,
                                          ErrorCode, IntermediateRequest,
                                          IntermediateResponse, Opcode,
                                          ServiceConfig)


class DummmyError(BaseException):
    pass


def ret_ids(objects):
    return {obj['id'] for obj in objects}


@pytest.fixture(scope='module', autouse=True)
def simulator_file_cleanup():
    yield
    rmtree('simulator/', ignore_errors=True)


@pytest.fixture
def block_args():
    return {
        'id': 'testobj',
        'type': 'TempSensorOneWire',
        'data': {
            'value': 12345,
            'offset': 20,
            'address': 'FF'
        }
    }


@pytest.fixture(autouse=True)
def m_publish(mocker):
    m = mocker.patch(blocks_api.__name__ + '.mqtt.publish', autospec=True)
    return m


@pytest.fixture(autouse=True)
def m_backup_dir(mocker, tmp_path):
    mocker.patch(backup_storage.__name__ + '.BASE_BACKUP_DIR', tmp_path / 'backup')


@pytest.fixture(autouse=True)
def m_simulator_dir(mocker, tmp_path):
    mocker.patch(stream_connection.__name__ + '.SIMULATION_CWD', tmp_path / 'simulator')


def repeated_blocks(ids, args):
    return [{
        'id': id,
        'type': args['type'],
        'data': args['data']
    } for id in ids]


@pytest.fixture
async def app(app):
    """App + controller routes"""
    config: ServiceConfig = app['config']
    app['ini'] = parse_ini(app)
    config['mock'] = False
    config['simulation'] = True
    config['isolated'] = True
    config['device_id'] = '123456789012345678901234'
    config['device_port'] = find_free_port()
    config['display_ws_port'] = 0  # let firmware find its own free port

    service_status.setup(app)
    scheduler.setup(app)
    codec.setup(app)
    connection.setup(app)
    commander.setup(app)
    block_store.setup(app)
    global_store.setup(app)
    service_store.setup(app)
    synchronization.setup(app)
    controller.setup(app)
    backup_storage.setup(app)

    error_response.setup(app)
    blocks_api.setup(app)
    backup_api.setup(app)
    system_api.setup(app)
    settings_api.setup(app)
    debug_api.setup(app)

    return app


@pytest.fixture
async def production_app(app):
    app['config']['debug'] = False
    return app


@pytest.fixture(autouse=True)
async def synchronized(app, client):
    # Prevents test hangups if the connection fails
    await asyncio.wait_for(service_status.wait_synchronized(app), timeout=5)


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
    # 400 if input fails schema check
    del block_args['type']
    retv = await response(client.post('/blocks/create', json=block_args), 400)
    assert retv == [{
        'in': 'body',
        'loc': ['type'],
        'msg': 'field required',
        'type': 'value_error.missing',
    }]

    # 400 if input fails encoding
    # This yields a JSON error
    block_args['type'] = 'dummy'
    retv = await response(client.post('/blocks/create', json=block_args), 400)
    assert 'dummy' in retv['error']
    assert 'traceback' in retv


async def test_invalid_input_prod(production_app, client, block_args):
    # 400 if input fails schema check
    del block_args['type']
    retv = await response(client.post('/blocks/create', json=block_args), 400)
    assert retv == [{
        'in': 'body',
        'loc': ['type'],
        'msg': 'field required',
        'type': 'value_error.missing',
    }]

    # 400 if input fails encoding
    # This yields a JSON error
    # For production errors, no traceback is returned
    block_args['type'] = 'dummy'
    retv = await response(client.post('/blocks/create', json=block_args), 400)
    assert 'dummy' in retv['error']
    assert 'traceback' not in retv


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


async def test_write(app, client, block_args, m_publish):
    await response(client.post('/blocks/create', json=block_args), 201)
    assert await response(client.post('/blocks/write', json=block_args))
    assert m_publish.call_count == 2


async def test_patch(app, client, block_args, m_publish):
    await response(client.post('/blocks/create', json=block_args), 201)
    assert await response(client.post('/blocks/patch', json=block_args))
    assert m_publish.call_count == 2


async def test_multipatch(app, client, block_args, m_publish):
    await response(client.post('/blocks/create', json=block_args), 201)
    assert await response(client.post('/blocks/multipatch', json=[block_args, block_args, block_args]))
    assert m_publish.call_count == 2


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
    store = block_store.fget(app)
    await response(client.post('/blocks/create', json=block_args), 201)
    store['unused', 456] = {}
    retv = await response(client.post('/blocks/cleanup'))
    assert {'id': 'unused', 'nid': 456, 'type': None, 'serviceId': 'test_app'} in retv
    assert not [v for v in retv if v['id'] == 'testobj']


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


async def test_sequence(app, client):
    setpoint_block = {
        'id': 'setpoint',
        'type': 'SetpointSensorPair',
        'data': {}
    }

    sequence_block = {
        'id': 'sequence',
        'type': 'Sequence',
        'data': {
            'enabled': True,
            'instructions': [
                'SET_SETPOINT target=setpoint, setting=40C',
                'WAIT_SETPOINT target=setpoint, precision=1dC',
                'RESTART',
            ]
        }
    }

    await response(client.post('/blocks/create', json=setpoint_block), 201)
    retd = await response(client.post('/blocks/create', json=sequence_block), 201)

    assert retd['data']['instructions'] == [
        'SET_SETPOINT target=setpoint, setting=40.0C',
        'WAIT_SETPOINT target=setpoint, precision=1.0dC',
        'RESTART',
    ]


async def test_ping(app, client):
    await response(client.get('/system/ping'))
    await response(client.post('/system/ping'))


async def test_settings_api(app, client, block_args):
    await response(client.post('/blocks/create', json=block_args), 201)

    retd = await response(client.get('/settings/autoconnecting'))
    assert retd == {'enabled': True}

    retd = await response(client.put('/settings/autoconnecting', json={'enabled': False}))
    assert retd == {'enabled': False}
    retd = await response(client.get('/settings/autoconnecting'))
    assert retd == {'enabled': False}


async def test_discover(app, client):
    resp = await response(client.post('/blocks/discover'))
    assert resp == []


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
            'enabled': True,
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
    assert 'ActiveGroups' not in resp_ids
    assert 'SystemInfo' in resp_ids

    # Add an obsolete system block
    data['blocks'].append({'nid': 1, 'type': 'Groups', 'data': {}})

    # Add an unused store alias
    data['store'].append({'keys': ['TROLOLOL', 9999], 'data': dict()})

    # Add renamed type to store data
    data['store'].append({'keys': ['renamed_display_settings', const.DISPLAY_SETTINGS_NID], 'data': dict()})

    # Add a Block that will fail to be created, and should be skipped
    data['blocks'].append({
        'id': 'derpface',
        'nid': 500,
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
    assert 'renamed_display_settings' in resp_ids
    assert 'derpface' not in resp_ids


async def test_backup_stored(app, client, block_args):
    portable = await response(client.post('/blocks/backup/save'))
    saved_stored = await response(client.post('/blocks/backup/stored/save', json={
        'name': 'stored',
    }))

    assert saved_stored['blocks']
    assert saved_stored['store']
    assert saved_stored['timestamp']
    assert saved_stored['firmware']
    assert saved_stored['device']

    assert len(portable['blocks']) == len(saved_stored['blocks'])

    download_stored = await response(client.post('/blocks/backup/stored/download', json={
        'name': 'stored',
    }))
    assert saved_stored == download_stored

    upload_stored = await response(client.post('/blocks/backup/stored/upload', json=download_stored))
    assert saved_stored == upload_stored

    download_stored['name'] = None
    await response(client.post('/blocks/backup/stored/upload', json=download_stored), status=400)

    all_stored = await response(client.post('/blocks/backup/stored/all'))
    assert all_stored == [{'name': 'stored'}]

    # Create block not in backup
    # Then restore backup
    await response(client.post('/blocks/create', json=block_args), 201)
    await response(client.post('/blocks/backup/stored/load', json={
        'name': 'stored',
    }))
    ids = ret_ids(await response(client.post('/blocks/all/read')))
    assert block_args['id'] not in ids


async def test_read_all_logged(app, client):
    args = {
        'id': 'pwm',
        'type': 'ActuatorPwm',
        'data': {
            'storedSetting': 80,  # logged
            'period': 2,  # not logged
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
    assert 'storedSetting' in obj_data
    assert 'period' in obj_data

    # log_objects strips all keys that are not explicitly marked as logged
    obj = logged[-1]
    assert args['id'] == obj['id']
    obj_data = obj['data']
    assert obj_data is not None
    assert 'storedSetting' in obj_data
    assert 'period' not in obj_data


async def test_system_status(app, client):
    await service_status.wait_synchronized(app)
    resp = await response(client.get('/system/status'))

    firmware_desc = {
        'firmware_version': ANY,
        'proto_version': ANY,
        'firmware_date': ANY,
        'proto_date': ANY,
    }

    device_desc = {
        'device_id': ANY,
    }

    assert resp == {
        'enabled': True,
        'service': {
            'name': 'test_app',
            'firmware': firmware_desc,
            'device': device_desc,
        },
        'controller': {
            'system_version': ANY,
            'platform': ANY,
            'reset_reason': ANY,
            'firmware': firmware_desc,
            'device': device_desc,
        },
        'address': 'brewblox-amd64.sim',
        'connection_kind': 'SIM',
        'connection_status': 'SYNCHRONIZED',
        'firmware_error': None,
        'identity_error': None,
    }

    service_status.set_disconnected(app)
    await asyncio.sleep(0.01)
    resp = await response(client.get('/system/status'))
    assert resp['connection_status'] == 'DISCONNECTED'
    assert resp['controller'] is None


async def test_system_resets(app, client, mocker):
    sys_api = system_api.__name__
    mocker.patch(sys_api + '.shutdown_soon', AsyncMock())

    await response(client.post('/system/reboot/service'))
    system_api.shutdown_soon.assert_awaited()

    await response(client.post('/system/reboot/controller'))
    await response(client.post('/system/clear_wifi'))
    await response(client.post('/system/factory_reset'))


async def test_debug_encode_request(app, client):
    payload = DecodedPayload(
        blockId=123,
        blockType='TempSensorOneWire',
        content={
            'value': 12345,
            'offset': 20,
            'address': 'FF'
        }
    )

    retv = await response(client.post('/_debug/encode_payload',
                                      json=payload.clean_dict()))
    payload = EncodedPayload(**retv)

    req = IntermediateRequest(
        msgId=1,
        opcode=Opcode.BLOCK_WRITE,
        payload=payload,
    )

    retv = await response(client.post('/_debug/encode_request',
                                      json=req.clean_dict()))
    assert retv['message']

    retv = await response(client.post('/_debug/decode_request',
                                      json=retv))
    req = IntermediateRequest(**retv)
    assert req.opcode == Opcode.BLOCK_WRITE

    retv = await response(client.post('/_debug/decode_payload',
                                      json=req.payload.clean_dict()))
    payload = DecodedPayload(**retv)

    assert payload.content['value']['value'] == 0  # Readonly value
    assert payload.content['offset']['value'] == 20


async def test_debug_encode_response(app, client):
    payload = DecodedPayload(
        blockId=123,
        blockType='TempSensorOneWire',
        content={
            'value': 12345,
            'offset': 20,
            'address': 'FF'
        }
    )
    retv = await response(client.post('/_debug/encode_payload',
                                      json=payload.clean_dict()))
    payload = EncodedPayload(**retv)

    resp = IntermediateResponse(
        msgId=1,
        error=ErrorCode.INVALID_BLOCK,
        payload=[payload],
    )
    retv = await response(client.post('/_debug/encode_response',
                                      json=resp.clean_dict()))
    assert retv['message']

    retv = await response(client.post('/_debug/decode_response',
                                      json=retv))
    resp = IntermediateResponse(**retv)
    assert resp.error == ErrorCode.INVALID_BLOCK

    retv = await response(client.post('/_debug/decode_payload',
                                      json=resp.payload[0].clean_dict()))
    payload = DecodedPayload(**retv)

    assert payload.content['value']['value'] == 0  # Readonly value
    assert payload.content['offset']['value'] == 20
