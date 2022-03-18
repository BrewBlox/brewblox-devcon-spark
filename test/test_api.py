"""
Tests brewblox_devcon_spark.api
"""

import asyncio
from unittest.mock import ANY, AsyncMock

import pytest
from brewblox_service import scheduler
from brewblox_service.testing import response

from brewblox_devcon_spark import (block_cache, block_store, codec, commander,
                                   connection_sim, const, controller,
                                   global_store, service_status, service_store,
                                   synchronization, ymodem)
from brewblox_devcon_spark.api import (blocks_api, debug_api, error_response,
                                       settings_api, system_api)
from brewblox_devcon_spark.models import ErrorCode, Opcode


class DummmyError(BaseException):
    pass


def ret_ids(objects):
    return {obj['id'] for obj in objects}


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


def repeated_blocks(ids, args):
    return [{
        'id': id,
        'type': args['type'],
        'data': args['data']
    } for id in ids]


@pytest.fixture
async def app(app, loop):
    """App + controller routes"""
    service_status.setup(app)
    scheduler.setup(app)
    codec.setup(app)
    connection_sim.setup(app)
    commander.setup(app)
    block_store.setup(app)
    block_cache.setup(app)
    global_store.setup(app)
    service_store.setup(app)
    synchronization.setup(app)
    controller.setup(app)

    error_response.setup(app)
    blocks_api.setup(app)
    system_api.setup(app)
    settings_api.setup(app)
    debug_api.setup(app)

    return app


@pytest.fixture
async def production_app(app, loop):
    app['config']['debug'] = False
    return app


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
    assert resp[0]['id'] == 'SparkPins'


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
    assert 'ActiveGroups' not in resp_ids
    assert 'SystemInfo' in resp_ids

    # Add an obsolete system block
    data['blocks'].append({'nid': 1, 'type': 'Groups', 'data': {}})

    # Add an unused store alias
    data['store'].append({'keys': ['TROLOLOL', 9999], 'data': dict()})

    # Add renamed type to store data
    data['store'].append({'keys': ['renamed_wifi', const.WIFI_SETTINGS_NID], 'data': dict()})

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
    assert 'renamed_wifi' in resp_ids
    assert 'derpface' not in resp_ids


async def test_read_all_logged(app, client):
    args = {
        'id': 'edgey',
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
    await service_status.wait_synchronized(app)
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
        'is_updating': False,
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
    mocker.patch(sys_api + '.FLUSH_PERIOD_S', 0.001)
    mocker.patch(sys_api + '.shutdown_soon', AsyncMock())
    mocker.patch(sys_api + '.mqtt.publish', AsyncMock())

    m_conn = mocker.patch(sys_api + '.ymodem.connect', autospec=True)
    m_conn.return_value = AsyncMock(ymodem.Connection)

    m_ota = mocker.patch(sys_api + '.ymodem.OtaClient', autospec=True)
    m_ota.return_value.transfer = AsyncMock()

    await response(client.post('/system/flash'))
    m_ota.return_value.send.assert_awaited()
    system_api.shutdown_soon.assert_awaited()


async def test_system_flash_sim(app, client):
    # Not implemented for simulations
    app['config']['simulation'] = True
    await response(client.post('/system/flash'), 424)


async def test_system_resets(app, client, mocker):
    sys_api = system_api.__name__
    mocker.patch(sys_api + '.shutdown_soon', AsyncMock())

    await response(client.post('/system/reboot/service'))
    system_api.shutdown_soon.assert_awaited()

    await response(client.post('/system/reboot/controller'))
    await response(client.post('/system/factory_reset'))


async def test_debug_encode(app, client):
    payload = {
        'blockId': 123,
        'blockType': 'TempSensorOneWire',
        'content': {
            'value': 12345,
            'offset': 20,
            'address': 'FF'
        },
    }

    # Encode normal (non-nested) message
    encoded = await response(client.post('/_debug/encode', json=payload))
    assert encoded['content']
    assert isinstance(encoded['content'], str)

    decoded = await response(client.post('/_debug/decode', json={
        'blockType': encoded['blockType'],
        'content': encoded['content'],
    }))
    addr = decoded['content']['address']
    assert addr.lower().startswith('ff')

    # Request has an embedded extra message
    request_msg = {
        'msgId': 1,
        'opcode': Opcode.BLOCK_WRITE.name,
        'payload': payload,
    }

    encoded = await response(client.post('/_debug/encode', json={
        'blockType': codec.REQUEST_TYPE,
        'content': request_msg,
    }))
    assert encoded['content']
    assert isinstance(encoded['content'], str)

    decoded = await response(client.post('/_debug/decode', json={
        'blockType': encoded['blockType'],
        'content': encoded['content']
    }))
    addr = decoded['content']['payload']['content']['address']
    assert addr.lower().startswith('ff')

    # Response has an embedded extra message
    response_msg = {
        'msgId': 1,
        'error': ErrorCode.INVALID_OPCODE.name,
        'payload': [payload, payload]
    }

    encoded = await response(client.post('/_debug/encode', json={
        'blockType': codec.RESPONSE_TYPE,
        'content': response_msg,
    }))
    assert encoded['content']
    assert isinstance(encoded['content'], str)

    decoded = await response(client.post('/_debug/decode', json={
        'blockType': encoded['blockType'],
        'content': encoded['content']
    }))
    addr = decoded['content']['payload'][1]['content']['address']
    assert addr.lower().startswith('ff')

    # args should be validated
    await response(client.post('/_debug/decode', json={
        'blockType': [1],
        'content': '',
    }), 400)

    # Payload is optional both ways
    request_msg = {
        'msgId': 1,
        'opcode': Opcode.BLOCK_WRITE.name,
        'payload': None,
    }
    encoded = await response(client.post('/_debug/encode', json={
        'blockType': codec.REQUEST_TYPE,
        'content': request_msg,
    }))
    await response(client.post('/_debug/decode', json={
        'blockType': encoded['blockType'],
        'content': encoded['content']
    }))

    # Errors are published
    retv = await response(client.post('/_debug/decode', json={
        'blockType': encoded['blockType'],
        'content': 'INVALID',
    }))
    assert retv['blockType'] == 'ErrorObject'
