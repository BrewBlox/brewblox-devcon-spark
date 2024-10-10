import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
from unittest.mock import ANY, Mock
from datetime import timedelta

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from pytest_httpx import HTTPXMock
from pytest_mock import MockerFixture

from brewblox_devcon_spark import (app_factory, block_backup, codec, command,
                                   connection, const, datastore_blocks,
                                   datastore_settings, endpoints, mqtt,
                                   spark_api, state_machine, synchronization,
                                   utils)
from brewblox_devcon_spark.models import (Backup, Block, BlockIdentity,
                                          DatastoreMultiQuery, DecodedPayload,
                                          EncodedMessage, EncodedPayload,
                                          ErrorCode, IntermediateRequest,
                                          IntermediateResponse, Opcode,
                                          UsbProxyResponse)


class DummmyError(BaseException):
    pass


def ret_ids(objects: list[dict | Block]) -> set[str]:
    try:
        return {obj['id'] for obj in objects}
    except TypeError:
        return {obj.id for obj in objects}


def repeated_blocks(ids: list[str], base: Block) -> list[Block]:
    return [Block(id=id, type=base.type, data=base.data)
            for id in ids]


@pytest.fixture
def block_args() -> Block:
    return Block(
        id='testobj',
        type='TempSensorOneWire',
        data={
            'value': 12345,
            'offset': 20,
            'address': 'FF'
        }
    )


@asynccontextmanager
async def clear_datastore():
    config = utils.get_config()
    client = AsyncClient(base_url=config.datastore_url)
    query = DatastoreMultiQuery(namespace=const.SERVICE_NAMESPACE, filter='*')
    content = query.model_dump(mode='json')
    await asyncio.wait_for(utils.httpx_retry(lambda: client.post('/mdelete', json=content)),
                           timeout=5)
    yield


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(clear_datastore())
        await stack.enter_async_context(mqtt.lifespan())
        # await stack.enter_async_context(datastore.lifespan())
        await stack.enter_async_context(connection.lifespan())
        await stack.enter_async_context(synchronization.lifespan())
        yield


@pytest.fixture
def app() -> FastAPI:
    config = utils.get_config()
    config.mock = False
    config.simulation = True
    config.command_timeout = timedelta(seconds=1)

    mqtt.setup()
    state_machine.setup()
    datastore_settings.setup()
    datastore_blocks.setup()
    codec.setup()
    connection.setup()
    command.setup()
    spark_api.setup()
    block_backup.setup()

    app = FastAPI(lifespan=lifespan)

    app_factory.add_exception_handlers(app)

    for router in endpoints.routers:
        app.include_router(router)

    return app


@pytest.fixture(autouse=True)
def s_publish(app: FastAPI, mocker: MockerFixture) -> Mock:
    m = mocker.spy(mqtt.CV.get(), 'publish')
    return m


@pytest.fixture(autouse=True)
async def synchronized(client: AsyncClient):
    state = state_machine.CV.get()
    # Prevents test hangups if the connection fails
    await asyncio.wait_for(state.wait_synchronized(),
                           timeout=5)


async def test_create(client: AsyncClient, block_args: Block):
    # Create object
    resp = await client.post('/blocks/create', json=block_args.model_dump())
    assert Block.model_validate_json(resp.text).id == block_args.id

    # Conflict error: name already taken
    resp = await client.post('/blocks/create', json=block_args.model_dump())
    assert resp.status_code == 500

    block_args.nid = 0
    block_args.id = 'other_obj'
    resp = await client.post('/blocks/create', json=block_args.model_dump())
    assert Block.model_validate_json(resp.text).id == block_args.id


async def test_invalid_input(client: AsyncClient, block_args: Block, mocker: MockerFixture):
    api = spark_api.CV.get()

    # 422 if input fails schema check
    raw = block_args.model_dump()
    del raw['type']
    resp = await client.post('/blocks/create', json=raw)
    assert resp.status_code == 422
    retv = resp.json()
    assert 'RequestValidationError' in retv['error']
    assert 'traceback' not in retv
    assert 'validation' in retv

    # 409 if input fails encoding
    raw = block_args.model_dump()
    raw['type'] = 'dummy'
    resp = await client.post('/blocks/create', json=raw)
    assert resp.status_code == 400
    retv = resp.json()
    assert 'dummy' in retv['error']
    assert 'traceback' in retv
    assert 'validation' not in retv

    # We need to simulate some bugs now
    m = mocker.patch.object(api, 'create_block', autospec=True)
    mocker.patch(endpoints.http_blocks.__name__ + '.publish')

    # 500 if output is invalid
    # This is a programming error
    m.side_effect = None
    m.return_value = BlockIdentity()
    resp = await client.post('/blocks/create', json=raw)
    assert resp.status_code == 500
    retv = resp.json()
    assert 'ResponseValidationError' in retv['error']
    assert 'traceback' not in retv
    assert 'validation' in retv


async def test_invalid_input_prod(client: AsyncClient, block_args: Block, mocker: MockerFixture):
    api = spark_api.CV.get()
    config = utils.get_config()
    config.debug = False

    # 422 if input fails schema check
    raw = block_args.model_dump()
    del raw['type']
    resp = await client.post('/blocks/create', json=raw)
    assert resp.status_code == 422
    retv = resp.json()
    assert 'RequestValidationError' in retv['error']
    assert 'traceback' not in retv
    assert 'validation' in retv

    # 409 if input fails encoding
    raw = block_args.model_dump()
    raw['type'] = 'dummy'
    resp = await client.post('/blocks/create', json=raw)
    assert resp.status_code == 400
    retv = resp.json()
    assert 'dummy' in retv['error']
    assert 'traceback' not in retv
    assert 'validation' not in retv

    # We need to simulate some bugs now
    m = mocker.patch.object(api, 'create_block', autospec=True)
    mocker.patch(endpoints.http_blocks.__name__ + '.publish')

    # 500 if output is invalid
    # This is a programming error
    m.side_effect = None
    m.return_value = BlockIdentity()
    resp = await client.post('/blocks/create', json=raw)
    assert resp.status_code == 500
    retv = resp.json()
    assert 'ResponseValidationError' in retv['error']
    assert 'traceback' not in retv
    assert 'validation' in retv


async def test_create_performance(client: AsyncClient, block_args: Block):
    num_items = 50
    ids = [f'id{num}' for num in range(num_items)]
    blocks = repeated_blocks(ids, block_args)

    await asyncio.gather(*(client.post('/blocks/create', json=block.model_dump(mode='json'))
                           for block in blocks))

    resp = await client.post('/blocks/all/read')
    assert set(ids).issubset(ret_ids(resp.json()))


async def test_batch_create_read_delete(client: AsyncClient, block_args: Block):
    num_items = 50
    ids = [f'id{num}' for num in range(num_items)]
    blocks = repeated_blocks(ids, block_args)
    raw_idents = [{'id': block.id} for block in blocks]
    raw_blocks = [block.model_dump(mode='json') for block in blocks]

    resp = await client.post('/blocks/batch/create', json=raw_blocks)
    assert resp.status_code == 201
    assert len(resp.json()) == num_items

    resp = await client.post('/blocks/batch/read', json=raw_idents)
    assert resp.status_code == 200
    assert len(resp.json()) == num_items

    resp = await client.post('/blocks/all/read')
    assert resp.status_code == 200
    assert set(ids).issubset(ret_ids(resp.json()))

    resp = await client.post('/blocks/batch/delete', json=raw_idents)
    assert resp.status_code == 200
    assert len(resp.json()) == num_items

    resp = await client.post('/blocks/all/read')
    assert set(ids).isdisjoint(ret_ids(resp.json()))


async def test_read(client: AsyncClient, block_args: Block):
    resp = await client.post('/blocks/read', json={'id': 'testobj'})
    assert resp.status_code == 400  # Block does not exist

    resp = await client.post('/blocks/create', json=block_args.model_dump())
    assert resp.status_code == 201

    resp = await client.post('/blocks/read', json={'id': 'testobj'})
    assert Block.model_validate_json(resp.text).id == 'testobj'


async def test_read_performance(client: AsyncClient, block_args: Block):
    resp = await client.post('/blocks/create', json=block_args.model_dump())
    assert resp.status_code == 201

    resps = await asyncio.gather(*(client.post('/blocks/read', json={'id': 'testobj'}) for _ in range(100)))
    for resp in resps:
        assert resp.status_code == 200


async def test_read_logged(client: AsyncClient, block_args: Block):
    resp = await client.post('/blocks/create', json=block_args.model_dump())
    assert resp.status_code == 201

    resp = await client.post('/blocks/read/logged', json={'id': 'testobj'})
    retd = Block.model_validate_json(resp.text)
    assert retd.id == 'testobj'
    assert 'address' not in retd.data  # address is not a logged field


async def test_write(client: AsyncClient, block_args: Block, s_publish: Mock):
    resp = await client.post('/blocks/create', json=block_args.model_dump())
    assert resp.status_code == 201

    resp = await client.post('/blocks/write', json=block_args.model_dump())
    assert resp.status_code == 200
    assert s_publish.call_count == 2


async def test_batch_write(client: AsyncClient, block_args: Block, s_publish: Mock):
    resp = await client.post('/blocks/create', json=block_args.model_dump())
    assert resp.status_code == 201

    resp = await client.post('/blocks/batch/write',
                             json=[block_args.model_dump(),
                                   block_args.model_dump(),
                                   block_args.model_dump()])
    assert resp.status_code == 200
    assert s_publish.call_count == 2


async def test_patch(client: AsyncClient, block_args: Block, s_publish: Mock):
    resp = await client.post('/blocks/create', json=block_args.model_dump())
    assert resp.status_code == 201

    resp = await client.post('/blocks/patch', json=block_args.model_dump())
    assert resp.status_code == 200
    assert s_publish.call_count == 2

    # Create block with only min constraint
    pwm_block = Block(id='pwm',
                      type='ActuatorPwm',
                      data={
                          'enabled': True,
                          'constraints': {
                              'min': {'value': 10},
                          },
                      })
    resp = await client.post('/blocks/create', json=pwm_block.model_dump())
    assert resp.status_code == 201

    # Add a max constraint in a patch
    pwm_block = Block(id='pwm',
                      type='ActuatorPwm',
                      data={
                          'constraints': {
                              'max': {'value': 100},
                          },
                      })
    resp = await client.post('/blocks/patch', json=pwm_block.model_dump())
    assert resp.status_code == 200

    patched = Block.model_validate_json(resp.text)
    assert patched.data['enabled'] is True
    assert patched.data['constraints'] == {
        'min': {'enabled': False, 'limiting': False, 'value': 10},
        'max': {'enabled': False, 'limiting': False, 'value': 100},
    }

    # Patch the max constraint to only edit the `enabled` field
    pwm_block = Block(id='pwm',
                      type='ActuatorPwm',
                      data={
                          'constraints': {
                              'max': {'enabled': True},
                          },
                      })
    resp = await client.post('/blocks/patch', json=pwm_block.model_dump())
    assert resp.status_code == 200

    patched = Block.model_validate_json(resp.text)
    assert patched.data['enabled'] is True
    assert patched.data['constraints'] == {
        'min': {'enabled': False, 'limiting': False, 'value': 10},
        'max': {'enabled': True, 'limiting': False, 'value': 100},
    }

    # Remove the max constraint in a patch
    pwm_block = Block(id='pwm',
                      type='ActuatorPwm',
                      data={
                          'constraints': {
                              'max': None,
                          },
                      })
    resp = await client.post('/blocks/patch', json=pwm_block.model_dump())
    assert resp.status_code == 200

    patched = Block.model_validate_json(resp.text)
    assert patched.data['enabled'] is True
    assert patched.data['constraints'] == {
        'min': {'enabled': False, 'limiting': False, 'value': 10},
    }


async def test_batch_patch(client: AsyncClient, block_args: Block, s_publish: Mock):
    resp = await client.post('/blocks/create', json=block_args.model_dump())
    assert resp.status_code == 201

    resp = await client.post('/blocks/batch/patch',
                             json=[block_args.model_dump(),
                                   block_args.model_dump(),
                                   block_args.model_dump()])
    assert resp.status_code == 200
    assert s_publish.call_count == 2


async def test_delete(client: AsyncClient, block_args: Block):
    resp = await client.post('/blocks/create', json=block_args.model_dump())
    assert resp.status_code == 201

    resp = await client.post('/blocks/delete', json={'id': 'testobj'})
    assert BlockIdentity.model_validate_json(resp.text).id == 'testobj'

    resp = await client.post('/blocks/read', json={'id': 'testobj'})
    assert resp.status_code == 400


async def test_nid_crud(client: AsyncClient, block_args: Block):
    resp = await client.post('/blocks/create', json=block_args.model_dump())
    assert resp.status_code == 201

    created = Block.model_validate_json(resp.text)

    created.data['value'] = 5
    resp = await client.post('/blocks/read', json={'nid': created.nid})
    assert resp.status_code == 200
    resp = await client.post('/blocks/write', json=created.model_dump())
    assert resp.status_code == 200
    resp = await client.post('/blocks/delete', json={'nid': created.nid})
    assert resp.status_code == 200

    resp = await client.post('/blocks/read', json={'nid': created.nid})
    assert resp.status_code == 500


async def test_stored_blocks(client: AsyncClient, block_args: Block):
    resp = await client.post('/blocks/all/read/stored')
    base_num = len(resp.json())

    resp = await client.post('/blocks/create', json=block_args.model_dump())
    assert resp.status_code == 201
    resp = await client.post('/blocks/all/read/stored')
    assert len(resp.json()) == 1 + base_num

    resp = await client.post('/blocks/read/stored', json={'id': 'testobj'})
    assert Block.model_validate_json(resp.text).id == 'testobj'

    resp = await client.post('/blocks/read/stored', json={'id': 'flappy'})
    assert resp.status_code == 400


async def test_delete_all(client: AsyncClient, block_args: Block):
    resp = await client.post('/blocks/all/read')
    n_sys_obj = len(resp.json())

    for i in range(5):
        block_args.id = f'id{i}'
        resp = await client.post('/blocks/create', json=block_args.model_dump())
        assert resp.status_code == 201

    resp = await client.post('/blocks/all/read')
    assert len(resp.json()) == n_sys_obj + 5

    resp = await client.post('/blocks/all/delete')
    assert len(resp.json()) == 5

    resp = await client.post('/blocks/all/read')
    assert len(resp.json()) == n_sys_obj


async def test_rename(client: AsyncClient, block_args: Block):
    resp = await client.post('/blocks/create', json=block_args.model_dump())
    assert resp.status_code == 201
    existing = block_args.id
    desired = 'newname'

    resp = await client.post('/blocks/read', json={'id': desired})
    assert resp.status_code == 400

    resp = await client.post('/blocks/rename', json={
        'existing': existing,
        'desired': desired,
    })
    assert resp.status_code == 200

    resp = await client.post('/blocks/read', json={'id': desired})
    assert resp.status_code == 200


async def test_sequence(client: AsyncClient):
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
                '   # This is a comment    ',
                'SET_SETPOINT target=setpoint, setting=40C',
                'WAIT_SETPOINT target=setpoint, precision=1dC',
                'RESTART',
            ]
        }
    }

    resp = await client.post('/blocks/create', json=setpoint_block)
    assert resp.status_code == 201

    resp = await client.post('/blocks/create', json=sequence_block)
    assert resp.status_code == 201
    block = Block.model_validate_json(resp.text)

    assert block.data['instructions'] == [
        '# This is a comment',
        'SET_SETPOINT target=setpoint, setting=40.0C',
        'WAIT_SETPOINT target=setpoint, precision=1.0dC',
        'RESTART',
    ]


async def test_ping(client: AsyncClient):
    resp = await client.get('/system/ping')
    assert resp.status_code == 200
    resp = await client.post('/system/ping')
    assert resp.status_code == 200


async def test_settings_api(client: AsyncClient, block_args: Block):
    resp = await client.post('/blocks/create', json=block_args.model_dump())
    assert resp.status_code == 201

    state = state_machine.CV.get()
    resp = await client.get('/settings/enabled')
    assert resp.json() == {'enabled': True}
    assert state.is_enabled()

    resp = await client.put('/settings/enabled', json={'enabled': False})
    assert resp.json() == {'enabled': False}
    assert not state.is_enabled()

    resp = await client.get('/settings/enabled')
    assert resp.json() == {'enabled': False}


async def test_discover(client: AsyncClient):
    resp = await client.post('/blocks/discover')
    assert resp.json() == []


async def test_validate(client: AsyncClient, block_args: Block):
    validate_args = {
        'type': block_args.type,
        'data': block_args.data,
    }
    resp = await client.post('/blocks/validate', json=validate_args)
    assert resp.status_code == 200

    invalid_data_obj = {
        'type': block_args.type,
        'data': {**block_args.data, 'invalid': True}
    }
    resp = await client.post('/blocks/validate', json=invalid_data_obj)
    assert resp.status_code == 400

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
    resp = await client.post('/blocks/validate', json=invalid_link_obj)
    assert resp.status_code == 400


async def test_backup_save(client: AsyncClient, block_args: Block):
    resp = await client.post('/blocks/backup/save')
    base_num = len(resp.json()['blocks'])

    resp = await client.post('/blocks/create', json=block_args.model_dump())
    assert resp.status_code == 201

    resp = await client.post('/blocks/backup/save')
    assert len(resp.json()['blocks']) == base_num + 1


async def test_backup_load(client: AsyncClient, spark_blocks: list[Block]):
    # reverse the set, to ensure some blocks link to later blocks
    backup = Backup(blocks=spark_blocks[::-1])

    resp = await client.post('/blocks/backup/load', json=backup.model_dump())
    assert resp.json() == {'messages': []}

    resp = await client.post('/blocks/all/read')
    ids = ret_ids(spark_blocks)
    resp_ids = ret_ids(resp.json())
    assert set(ids).issubset(resp_ids)
    assert 'ActiveGroups' not in resp_ids
    assert 'SystemInfo' in resp_ids

    # Add an obsolete system block
    backup.blocks.append(Block(
        nid=1,
        type='Groups',
        data={},
    ))

    # Add a block that has an unknown link
    backup.blocks.append(Block(
        id='fantast',
        nid=400,
        type='SetpointSensorPair',
        data={'sensorId<>': 'going to another high school'}
    ))

    # Add a Block that will fail to be created, and should be skipped
    backup.blocks.append(Block(
        id='derpface',
        nid=500,
        type='INVALID',
        data={}
    ))

    backup.blocks.append(Block(
        id='sensor-onewire-old',
        nid=500,
        type='TempSensorOneWire',
        data={
            'value[celsius]': 20.89789201,
             'offset[delta_degC]': 9,
            'address': 'DEADBEEF',
            'oneWireBusId<>': 'OneWireBus',
        },
    ))

    resp = await client.post('/blocks/backup/load', json=backup.model_dump())
    resp = resp.json()['messages']
    assert len(resp) == 3
    assert 'fantast' in resp[0]
    assert 'Groups' in resp[1]
    assert 'derpface' in resp[2]

    resp = await client.post('/blocks/all/read')
    resp_ids = ret_ids(resp.json())
    assert 'derpface' not in resp_ids


async def test_backup_stored(client: AsyncClient, block_args: Block):
    resp = await client.post('/blocks/backup/save')
    portable = Backup.model_validate_json(resp.text)

    resp = await client.post('/blocks/backup/stored/save', json={'name': 'stored'})
    saved_stored = Backup.model_validate_json(resp.text)

    assert len(portable.blocks) == len(saved_stored.blocks)

    resp = await client.post('/blocks/backup/stored/download', json={'name': 'stored'})
    download_stored = Backup.model_validate_json(resp.text)

    assert saved_stored == download_stored

    resp = await client.post('/blocks/backup/stored/upload', json=download_stored.model_dump())
    upload_stored = Backup.model_validate_json(resp.text)

    assert saved_stored == upload_stored

    download_stored.name = None
    resp = await client.post('/blocks/backup/stored/upload', json=download_stored.model_dump())
    assert resp.status_code == 400

    resp = await client.post('/blocks/backup/stored/all')
    assert resp.json() == [{'name': 'stored'}]

    # Create block not in backup
    # Then restore backup
    resp = await client.post('/blocks/create', json=block_args.model_dump())
    assert resp.status_code == 201

    resp = await client.post('/blocks/backup/stored/load', json={'name': 'stored'})
    assert resp.status_code == 200

    resp = await client.post('/blocks/all/read')
    assert block_args.id not in ret_ids(resp.json())


async def test_read_all_logged(client: AsyncClient):
    args = {
        'id': 'pwm',
        'type': 'ActuatorPwm',
        'data': {
            'storedSetting': 80,  # logged
            'period': 2,  # not logged
        }
    }

    resp = await client.post('/blocks/create', json=args)
    assert resp.status_code == 201

    resp = await client.post('/blocks/all/read')
    all = resp.json()

    resp = await client.post('/blocks/all/read/logged')
    logged = resp.json()

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


async def test_system_status(client: AsyncClient):
    config = utils.get_config()
    fw_config = utils.get_fw_config()
    resp = await client.get('/system/status')
    desc = resp.json()

    firmware_desc = {
        'firmware_version': fw_config.firmware_version,
        'proto_version': fw_config.proto_version,
        'firmware_date': fw_config.firmware_date,
        'proto_date': fw_config.proto_date,
    }

    device_desc = {
        'device_id': config.device_id,
    }

    assert desc == {
        'enabled': True,
        'service': {
            'name': 'sparkey',
            'firmware': firmware_desc,
            'device': device_desc,
        },
        'controller': {
            'system_version': ANY,
            'platform': ANY,
            'reset_reason': 'NONE',
            'firmware': firmware_desc,
            'device': device_desc,
        },
        'address': 'brewblox-amd64.sim',
        'discovery_kind': 'SIM',
        'connection_kind': 'SIM',
        'connection_status': 'SYNCHRONIZED',
        'firmware_error': None,
        'identity_error': None,
    }

    await command.CV.get().end_connection()

    resp = await client.get('/system/status')
    desc = resp.json()

    assert desc['connection_status'] == 'DISCONNECTED'
    assert desc['controller'] is None


async def test_system_usb(client: AsyncClient, httpx_mock: HTTPXMock):
    resp = await client.post('/system/usb')
    data = UsbProxyResponse.model_validate_json(resp.text)
    assert not data.enabled
    assert data.devices == []

    httpx_mock.add_response(url='http://usb-proxy:5000/usb-proxy/discover/_',
                            json={
                                '12345': 9000,
                                '23456': None,
                            })
    resp = await client.post('/system/usb')
    data = UsbProxyResponse.model_validate_json(resp.text)
    assert data.enabled
    assert data.devices == ['12345', '23456']


async def test_system_resets(client: AsyncClient, m_kill: Mock):
    await client.post('/system/reboot/service')
    m_kill.assert_called_once()

    await client.post('/system/reboot/controller')
    await client.post('/system/clear_wifi')
    await client.post('/system/factory_reset')


async def test_system_flash(client: AsyncClient, m_kill: Mock):
    state = state_machine.CV.get()

    resp = await client.post('/system/flash')
    assert resp.status_code == 424  # incompatible firmware
    assert m_kill.call_count == 0
    assert state.is_synchronized()

    desc = state.desc()
    desc.connection_kind = 'TCP'
    desc.controller.platform == 'dummy'  # not handled, but also not an error
    resp = await client.post('/system/flash')
    assert resp.status_code == 200
    assert m_kill.call_count == 1
    assert not state.is_connected()


async def test_debug_encode_request(client: AsyncClient):
    payload = DecodedPayload(
        blockId=123,
        blockType='TempSensorOneWire',
        content={
            'value': 12345,
            'offset': 20,
            'address': 'FF'
        }
    )

    resp = await client.post('/_debug/encode_payload', json=payload.model_dump(mode='json'))
    payload = EncodedPayload.model_validate_json(resp.text)

    req = IntermediateRequest(
        msgId=1,
        opcode=Opcode.BLOCK_WRITE,
        payload=payload,
    )

    resp = await client.post('/_debug/encode_request', json=req.model_dump(mode='json'))
    msg = EncodedMessage.model_validate_json(resp.text)

    resp = await client.post('/_debug/decode_request', json=msg.model_dump(mode='json'))
    req = IntermediateRequest.model_validate_json(resp.text)

    assert req.opcode == Opcode.BLOCK_WRITE

    resp = await client.post('/_debug/decode_payload', json=req.payload.model_dump(mode='json'))
    payload = DecodedPayload.model_validate_json(resp.text)

    assert payload.content['value']['value'] == 0  # Readonly value
    assert payload.content['offset']['value'] == 20


async def test_debug_encode_response(client: AsyncClient):
    payload = DecodedPayload(
        blockId=123,
        blockType='TempSensorOneWire',
        content={
            'value': 12345,
            'offset': 20,
            'address': 'FF'
        }
    )

    resp = await client.post('/_debug/encode_payload', json=payload.model_dump(mode='json'))
    payload = EncodedPayload.model_validate_json(resp.text)

    iresp = IntermediateResponse(
        msgId=1,
        error=ErrorCode.INVALID_BLOCK,
        payload=[payload],
    )
    resp = await client.post('/_debug/encode_response', json=iresp.model_dump(mode='json'))
    msg = EncodedMessage.model_validate_json(resp.text)

    resp = await client.post('/_debug/decode_response', json=msg.model_dump(mode='json'))
    iresp = IntermediateResponse.model_validate_json(resp.text)

    assert iresp.error == ErrorCode.INVALID_BLOCK
    assert len(iresp.payload) == 1

    payload = iresp.payload[0]
    resp = await client.post('/_debug/decode_payload', json=payload.model_dump(mode='json'))
    payload = DecodedPayload.model_validate_json(resp.text)

    assert payload.content['value']['value'] == 0  # Readonly value
    assert payload.content['offset']['value'] == 20
