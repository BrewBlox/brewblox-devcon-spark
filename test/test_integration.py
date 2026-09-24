import asyncio
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import timedelta
from unittest.mock import ANY, Mock

import pytest
from fastapi import FastAPI
from google.protobuf.descriptor import Descriptor
from httpx import AsyncClient
from pytest_httpx import HTTPXMock
from pytest_mock import MockerFixture

from brewblox_devcon_spark import (
    app_factory,
    block_backup,
    broadcast,
    codec,
    command,
    connection,
    const,
    datastore_blocks,
    datastore_settings,
    endpoints,
    exceptions,
    mqtt,
    spark_api,
    state_machine,
    synchronization,
    utils,
)
from brewblox_devcon_spark.models import (
    Backup,
    Block,
    BlockIdentity,
    DatastoreMultiQuery,
    DecodedPayload,
    EncodedMessage,
    EncodedPayload,
    ErrorCode,
    IntermediateRequest,
    IntermediateResponse,
    Opcode,
    ReadMode,
    UsbProxyResponse,
)


class DummmyError(BaseException):
    pass


def ret_ids(objects: list[dict | Block]) -> set[str]:
    try:
        return {obj['id'] for obj in objects}
    except TypeError:
        return {obj.id for obj in objects}


def repeated_blocks(ids: list[str], base: Block) -> list[Block]:
    return [Block(id=id, type=base.type, data=base.data) for id in ids]


@pytest.fixture
def block_args() -> Block:
    return Block(id='testobj', type='TempSensorOneWire', data={'value': 12345, 'offset': 20, 'address': 'FF'})


@asynccontextmanager
async def clear_datastore():
    config = utils.get_config()
    client = AsyncClient(base_url=config.datastore_url)
    query = DatastoreMultiQuery(namespace=const.SERVICE_NAMESPACE, filter='*')
    content = query.model_dump(mode='json')
    await asyncio.wait_for(utils.httpx_retry(lambda: client.post('/mdelete', json=content)), timeout=5)
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
    await asyncio.wait_for(state.wait_synchronized(), timeout=5)


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

    await asyncio.gather(*(client.post('/blocks/create', json=block.model_dump(mode='json')) for block in blocks))

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

    # Write is an alias of patch: absent fields are kept
    resp = await client.post('/blocks/write', json={'id': 'testobj', 'type': block_args.type, 'data': {'offset': 5}})
    assert resp.status_code == 200
    written = Block.model_validate_json(resp.text)
    assert written.data['offset']['value'] == 5
    assert written.data['address'] == 'ff00000000000000'


async def test_batch_write(client: AsyncClient, block_args: Block, s_publish: Mock):
    resp = await client.post('/blocks/create', json=block_args.model_dump())
    assert resp.status_code == 201

    resp = await client.post(
        '/blocks/batch/write', json=[block_args.model_dump(), block_args.model_dump(), block_args.model_dump()]
    )
    assert resp.status_code == 200
    assert s_publish.call_count == 2


async def test_patch(client: AsyncClient, block_args: Block, s_publish: Mock):
    resp = await client.post('/blocks/create', json=block_args.model_dump())
    assert resp.status_code == 201

    resp = await client.post('/blocks/patch', json=block_args.model_dump())
    assert resp.status_code == 200
    assert s_publish.call_count == 2

    async def patch(data: dict) -> dict:
        resp = await client.post('/blocks/patch', json={'id': 'pwm', 'type': 'ActuatorPwm', 'data': data})
        assert resp.status_code == 200
        return resp.json()['data']

    def constraints(**changed: dict) -> dict:
        """A DEFAULT read carries every constraint: the ones not set are disabled and zero"""
        unset = {
            'min': {'enabled': False, 'limiting': False, 'value': 0},
            'max': {'enabled': False, 'limiting': False, 'value': 0},
            'balanced': {
                'enabled': False,
                'limiting': False,
                'granted': 0,
                'balancerId': {'__bloxtype': 'Link', 'type': 'BalancerInterface', 'id': None},
            },
        }
        return {k: {**v, **changed.get(k, {})} for k, v in unset.items()}

    # Create block with only min constraint
    pwm_block = Block(
        id='pwm',
        type='ActuatorPwm',
        data={
            'enabled': True,
            'period[s]': 4,
            'constraints': {
                'min': {'value': 10},
            },
        },
    )
    resp = await client.post('/blocks/create', json=pwm_block.model_dump())
    assert resp.status_code == 201

    # Add a max constraint in a patch. Absent fields are kept.
    data = await patch({'constraints': {'max': {'value': 100}}})
    assert data['enabled'] is True
    assert data['period']['value'] == 4
    assert data['constraints'] == constraints(min={'value': 10}, max={'value': 100})

    # Patch the max constraint to only edit the `enabled` field
    data = await patch({'constraints': {'max': {'enabled': True}}})
    assert data['enabled'] is True
    assert data['constraints'] == constraints(min={'value': 10}, max={'enabled': True, 'value': 100})

    # Zero and false are written
    data = await patch({'enabled': False, 'period[s]': 0, 'constraints': {'min': {'value': 0}}})
    assert data['enabled'] is False
    assert data['period']['value'] == 0
    assert data['constraints'] == constraints(max={'enabled': True, 'value': 100})

    # Null resets a field to its default, and an absent field is kept.
    # A null constraint is disabled and zeroed.
    data = await patch({'enabled': True, 'period[s]': 4})
    data = await patch({'period': None, 'constraints': {'max': None}})
    assert data['enabled'] is True
    assert data['period']['value'] == 0
    assert data['constraints'] == constraints()

    data = await patch({'enabled': None, 'constraints': {'min': {'enabled': True, 'value': None}}})
    assert data['enabled'] is False
    assert data['constraints'] == constraints(min={'enabled': True})


async def test_patch_null_number(client: AsyncClient):
    """
    A cleared number field in the UI is sent as null: it resets the field to 0.
    (TempSensorAnalog spec overrides, where 0 means the spec default, are not in the simulator build:
    test_spark_api.py::test_patch_null covers them with the mock.)
    """

    async def post(url: str, data: dict) -> dict:
        resp = await client.post(url, json={'id': 'mock', 'type': 'ActuatorAnalogMock', 'data': data})
        assert resp.status_code in [200, 201], resp.text
        return resp.json()['data']

    data = await post('/blocks/create', {'enabled': True, 'storedSetting': 50, 'minSetting': 10, 'maxSetting': 90})
    assert data['minSetting'] == 10

    data = await post('/blocks/patch', {'minSetting': None, 'storedSetting': 5})
    assert data['minSetting'] == 0
    assert data['maxSetting'] == 90
    assert data['storedSetting'] == 5
    assert data['enabled'] is True


async def test_patch_lists(client: AsyncClient):
    """List fields are written whole: an empty list clears them, and an absent one keeps them"""

    async def post(url: str, block: dict) -> dict:
        resp = await client.post(url, json=block)
        assert resp.status_code in [200, 201], resp.text
        return resp.json()['data']

    def points(values: list[int]) -> list[dict]:
        return [{'time[s]': 10 * (idx + 1), 'temperature[degC]': v} for idx, v in enumerate(values)]

    def temps(data: dict) -> list[float]:
        return [v['temperature']['value'] for v in data['points']]

    profile = {'id': 'profile', 'type': 'SetpointProfile'}
    data = await post('/blocks/create', {**profile, 'data': {'points': points([20, 30])}})
    assert temps(data) == [20, 30]

    data = await post('/blocks/patch', {**profile, 'data': {'enabled': False}})
    assert temps(data) == [20, 30]

    data = await post('/blocks/patch', {**profile, 'data': {'points': points([25])}})
    assert temps(data) == [25]

    data = await post('/blocks/patch', {**profile, 'data': {'points': []}})
    assert data['points'] == []

    data = await post('/blocks/read', profile)
    assert data['points'] == []

    # Null clears a list too
    data = await post('/blocks/patch', {**profile, 'data': {'points': points([25])}})
    assert temps(data) == [25]
    data = await post('/blocks/patch', {**profile, 'data': {'points': None}})
    assert data['points'] == []

    # A system block
    display = {'id': 'DisplaySettings', 'type': 'DisplaySettings'}
    widget = {'pos': 1, 'color': 'aa0088', 'name': 'profile', 'tempSensor<>': None}
    data = await post('/blocks/patch', {**display, 'data': {'widgets': [widget], 'name': 'display'}})
    assert [v['name'] for v in data['widgets']] == ['profile']

    data = await post('/blocks/patch', {**display, 'data': {'name': 'renamed'}})
    assert [v['name'] for v in data['widgets']] == ['profile']

    data = await post('/blocks/patch', {**display, 'data': {'widgets': []}})
    assert data['widgets'] == []
    assert data['name'] == 'renamed'

    data = await post('/blocks/patch', {**display, 'data': {'widgets': [widget], 'name': None}})
    assert [v['name'] for v in data['widgets']] == ['profile']
    assert data['name'] == ''
    data = await post('/blocks/patch', {**display, 'data': {'widgets': None}})
    assert data['widgets'] == []


async def test_patch_variables(client: AsyncClient):
    """The firmware merges the Variables map by key: other keys are kept, and `empty` deletes a key"""

    async def post(url: str, block: dict) -> dict:
        resp = await client.post(url, json=block)
        assert resp.status_code in [200, 201], resp.text
        return resp.json()['data']['variables']

    variables = {'id': 'variables', 'type': 'Variables'}
    data = await post('/blocks/create', {**variables, 'data': {'variables': {'a': {'analog': 1}, 'b': {'analog': 2}}}})
    assert data == {'a': {'analog': 1}, 'b': {'analog': 2}}

    data = await post('/blocks/patch', {**variables, 'data': {'variables': {'b': {'analog': 3}, 'c': {'analog': 4}}}})
    assert data == {'a': {'analog': 1}, 'b': {'analog': 3}, 'c': {'analog': 4}}

    data = await post('/blocks/patch', {**variables, 'data': {'variables': {'a': {'empty': True}}}})
    assert data == {'b': {'analog': 3}, 'c': {'analog': 4}}

    data = await post('/blocks/patch', {**variables, 'data': {'variables': {}}})
    assert data == {'b': {'analog': 3}, 'c': {'analog': 4}}

    data = await post('/blocks/patch', {**variables, 'data': {}})
    assert data == {'b': {'analog': 3}, 'c': {'analog': 4}}

    # A null entry deletes its key, as `empty` does
    data = await post('/blocks/patch', {**variables, 'data': {'variables': {'b': None, 'd': {'analog': 5}}}})
    assert data == {'c': {'analog': 4}, 'd': {'analog': 5}}

    # A null map is a present, empty map: it changes nothing
    data = await post('/blocks/patch', {**variables, 'data': {'variables': None}})
    assert data == {'c': {'analog': 4}, 'd': {'analog': 5}}


ZERO_LINK = {'__bloxtype': 'Link', 'type': 'Any', 'id': None}
ZERO_VARIABLES = {
    'zero': {'timestamp': None},
    'time': {'timestamp': '2023-11-14T22:13:20Z'},
    'nolink': {'link': ZERO_LINK},
    'analog': {'analog': 1},
}
ZERO_INSTRUCTIONS = [
    'WAIT_UNTIL time=0',
    'WAIT_UNTIL time=2023-11-14T22:13:20Z',
    'SET_SETPOINT target=0, setting=20.0C',
    '#',
    'RESTART',
]


async def create_zero_members(client: AsyncClient) -> Callable[[], Awaitable[None]]:
    """
    Creates a Variables block with a zero timestamp and no link next to other variables,
    and a Sequence with WAIT_UNTIL time=0, a target of 0 and an empty comment. Returns a check that both read unchanged.
    A zero timestamp and no link read as null, and time=0 and target=0 read as written.
    """

    async def post(url: str, block: dict) -> dict:
        resp = await client.post(url, json=block)
        assert resp.status_code in [200, 201], resp.text
        return resp.json()['data']

    # The UI stores a new timestamp variable as 0
    variables = {**ZERO_VARIABLES, 'zero': {'timestamp': 0}}
    data = await post('/blocks/create', {'id': 'variables', 'type': 'Variables', 'data': {'variables': variables}})
    assert data['variables'] == ZERO_VARIABLES

    data = {'enabled': False, 'instructions': ZERO_INSTRUCTIONS}
    data = await post('/blocks/create', {'id': 'sequence', 'type': 'Sequence', 'data': data})
    assert data['instructions'] == ZERO_INSTRUCTIONS

    async def check():
        assert (await post('/blocks/read', {'id': 'variables'}))['variables'] == ZERO_VARIABLES
        assert (await post('/blocks/read', {'id': 'sequence'}))['instructions'] == ZERO_INSTRUCTIONS

    return check


async def test_zero_members_patch(client: AsyncClient):
    """Writing a read back changes nothing"""
    check = await create_zero_members(client)

    for block in [{'id': 'variables', 'type': 'Variables'}, {'id': 'sequence', 'type': 'Sequence'}]:
        resp = await client.post('/blocks/read', json=block)
        resp = await client.post('/blocks/patch', json={**block, 'data': resp.json()['data']})
        assert resp.status_code == 200, resp.text
        await check()


async def test_zero_members_backup(client: AsyncClient):
    """A backup save and load changes nothing"""
    check = await create_zero_members(client)

    resp = await client.post('/blocks/backup/save')
    resp = await client.post('/blocks/backup/load', json=resp.json())
    assert resp.json() == {'messages': []}
    await check()


async def test_batch_patch(client: AsyncClient, block_args: Block, s_publish: Mock):
    resp = await client.post('/blocks/create', json=block_args.model_dump())
    assert resp.status_code == 201

    resp = await client.post(
        '/blocks/batch/patch', json=[block_args.model_dump(), block_args.model_dump(), block_args.model_dump()]
    )
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

    resp = await client.post(
        '/blocks/rename',
        json={
            'existing': existing,
            'desired': desired,
        },
    )
    assert resp.status_code == 200

    resp = await client.post('/blocks/read', json={'id': desired})
    assert resp.status_code == 200


async def test_sequence(client: AsyncClient):
    setpoint_block = {'id': 'setpoint', 'type': 'SetpointSensorPair', 'data': {}}

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
            ],
        },
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

    invalid_data_obj = {'type': block_args.type, 'data': {**block_args.data, 'invalid': True}}
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
            'filterThreshold': 2,
        },
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
    backup.blocks.append(
        Block(
            nid=1,
            type='Groups',
            data={},
        )
    )

    # Add a block that has an unknown link
    backup.blocks.append(
        Block(id='fantast', nid=400, type='SetpointSensorPair', data={'sensorId<>': 'going to another high school'})
    )

    # Add a Block that will fail to be created, and should be skipped
    backup.blocks.append(Block(id='derpface', nid=500, type='INVALID', data={}))

    backup.blocks.append(
        Block(
            id='sensor-onewire-old',
            nid=500,
            type='TempSensorOneWire',
            data={
                'value[celsius]': 20.89789201,
                'offset[delta_degC]': 9,
                'address': 'DEADBEEF',
                'oneWireBusId<>': 'OneWireBus',
            },
        )
    )

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
        },
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
            'reset_reason': 'POWER_ON',
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


@pytest.mark.httpx_mock(assert_all_requests_were_expected=False)
async def test_system_usb(client: AsyncClient, httpx_mock: HTTPXMock):
    resp = await client.post('/system/usb')
    data = UsbProxyResponse.model_validate_json(resp.text)
    assert not data.enabled
    assert data.devices == []

    httpx_mock.add_response(
        url='http://usb-proxy:5000/usb-proxy/discover/_',
        json={
            '12345': 9000,
            '23456': None,
        },
    )
    resp = await client.post('/system/usb')
    data = UsbProxyResponse.model_validate_json(resp.text)
    assert data.enabled
    assert data.devices == ['12345', '23456']


async def test_system_resets(client: AsyncClient, m_kill: Mock):
    await client.post('/system/reboot/service')
    m_kill.assert_called_once()

    await client.post('/system/reboot/controller')
    await client.post('/system/clear_wifi')


async def test_system_clear_wifi_timeout(client: AsyncClient, mocker: MockerFixture):
    # Clearing wifi may drop the connection before the controller answers.
    # Whether the simulator answers in time is a race, so force the timeout.
    mocker.patch.object(
        spark_api.SparkApi,
        'clear_wifi',
        side_effect=exceptions.CommandTimeout('CLEAR_WIFI'),
    )
    resp = await client.post('/system/clear_wifi')
    assert resp.status_code == 200


async def test_system_factory_reset(client: AsyncClient):
    # Factory reset may timeout as the device disconnects
    resp = await client.post('/system/factory_reset')
    # Accept either 200 (success) or 424 (timeout/disconnected)
    assert resp.status_code in [200, 424]


async def test_system_flash(client: AsyncClient, m_kill: Mock):
    state = state_machine.CV.get()

    resp = await client.post('/system/flash')
    assert resp.status_code == 424  # incompatible firmware
    assert m_kill.call_count == 0
    assert state.is_synchronized()

    desc = state.desc()
    desc.connection_kind = 'TCP'
    if desc.controller:
        desc.controller.platform = 'dummy'  # not handled, but also not an error
    resp = await client.post('/system/flash')
    assert resp.status_code == 200
    assert m_kill.call_count == 1
    assert not state.is_connected()


async def test_debug_encode_request(client: AsyncClient):
    payload = DecodedPayload(
        blockId=123, blockType='TempSensorOneWire', content={'value': 12345, 'offset': 20, 'address': 'FF'}
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

    assert payload.content['value']['value'] is None  # Readonly: stripped on encode, and absent is invalid
    assert payload.content['offset']['value'] == 20


async def test_debug_encode_response(client: AsyncClient):
    payload = DecodedPayload(
        blockId=123, blockType='TempSensorOneWire', content={'value': 12345, 'offset': 20, 'address': 'FF'}
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

    assert payload.content['value']['value'] is None  # Readonly: stripped on encode, and absent is invalid
    assert payload.content['offset']['value'] == 20


async def test_get_free_port():
    # test for coverage, because tests get their free port from pytest_asyncio
    port = utils.get_free_port()
    assert 0 < port < 65536


def descriptor(block_type: str) -> Descriptor:
    return next(v for v in codec.lookup.CV_OBJECTS.get() if v.type_str == block_type).message_cls.DESCRIPTOR


async def test_changed_read(client: AsyncClient, block_args: Block):
    cmder = command.CV.get()

    # The first CHANGED read of a connection has the blocks with covered fields
    blocks = await cmder.read_all_blocks()
    changed = await cmder.read_all_blocks(ReadMode.CHANGED)
    assert changed
    assert {v.nid for v in changed} == {v.nid for v in blocks if codec.descriptors.coverage(descriptor(v.type))}

    # Nothing changed since
    assert await cmder.read_all_blocks(ReadMode.CHANGED) == []

    # A created block is changed. CHANGED reads have no names.
    resp = await client.post('/blocks/create', json=block_args.model_dump())
    created = Block.model_validate_json(resp.text)
    changed = await cmder.read_all_blocks(ReadMode.CHANGED)
    assert created.nid in {v.nid for v in changed}
    assert all(not v.id for v in changed)

    # A VERSION request starts a session: the next CHANGED read has every block with covered fields again.
    # Devcon sends one at every sync, so a reconnect on a transport that keeps its reader identity
    # (ESP USB, MQTT) still starts with a full CHANGED read.
    blocks = await cmder.read_all_blocks()
    await cmder.version()
    changed = await cmder.read_all_blocks(ReadMode.CHANGED)
    assert {v.nid for v in changed} == {v.nid for v in blocks if codec.descriptors.coverage(descriptor(v.type))}
    assert await cmder.read_all_blocks(ReadMode.CHANGED) == []


def time_varying(block_type: str) -> set[str]:
    """Fields that change with time, and that CHANGED reads do not update"""
    fields = descriptor(block_type).fields
    varying = {f.name for f in fields if codec.descriptors.options(f).skip_changed}
    if block_type == 'SysInfo':
        varying.add('systemTime')
    return varying


async def test_changed_merge(client: AsyncClient):
    """A cache that follows a full read with CHANGED reads and writes has what the next full read has"""
    state = state_machine.CV.get()
    cmder = command.CV.get()
    api = spark_api.CV.get()

    cache = broadcast.BlockCache()
    cache.reset(state.session)
    cmder.on_block_change = cache.on_block_change

    for block in [
        Block(id='sensor', type='TempSensorMock', data={'setting[degC]': 20, 'connected': True}),
        Block(
            id='pair',
            type='SetpointSensorPair',
            data={'sensorId<>': 'sensor', 'storedSetting[degC]': 21, 'enabled': True, 'filter': 'FILTER_NONE'},
        ),
        Block(id='balancer', type='Balancer', data={}),
        Block(
            id='pwm',
            type='ActuatorPwm',
            data={
                'enabled': True,
                'period[s]': 4,
                'constraints': {
                    'min': {'enabled': True, 'value': 10},
                    'max': {'enabled': True, 'value': 40},
                    'balanced': {'enabled': True, 'balancerId<>': 'balancer'},
                },
            },
        ),
        Block(
            id='pid',
            type='Pid',
            data={'inputId<>': 'pair', 'outputId<>': 'pwm', 'enabled': True, 'kp[1/degC]': 10, 'ti[s]': 0},
        ),
        Block(
            id='profile',
            type='SetpointProfile',
            data={'targetId<>': 'pair', 'enabled': False, 'points': [{'time[s]': 10, 'temperature[degC]': 20}]},
        ),
    ]:
        await api.create_block(block)

    store = datastore_blocks.CV.get()

    def cached(sid: str) -> dict:
        return cache.entries[store[sid]].data

    await cmder.read_all_blocks()
    await cmder.read_all_blocks(ReadMode.CHANGED)

    # Stored fields are written through, and the readonly state that follows from them is read
    await api.patch_block(Block(id='sensor', type='TempSensorMock', data={'setting[degC]': 25}))
    await api.patch_block(Block(id='pair', type='SetpointSensorPair', data={'storedSetting[degC]': 30}))
    await api.patch_block(Block(id='pwm', type='ActuatorPwm', data={'constraints': {'min': {'value': 5}}}))
    await api.patch_block(Block(id='profile', type='SetpointProfile', data={'points': []}))
    await api.patch_block(
        Block(
            id='DisplaySettings', type='DisplaySettings', data={'widgets': [{'pos': 1, 'name': 'pid', 'pid<>': 'pid'}]}
        )
    )

    # Only CHANGED reads bring the readonly state that follows from the writes
    pid_error = cached('pid')['error']
    for _ in range(30):
        await asyncio.sleep(0.1)
        await cmder.read_all_blocks(ReadMode.CHANGED)
        if cached('pwm')['constraints']['max']['limiting']:
            break

    assert cached('pair')['value']['value'] == 25
    assert cached('pid')['error']['value'] == 5
    assert pid_error['value'] != 5
    assert cached('pid')['p'] == 50
    assert cached('pwm')['setting'] == 40
    assert [v['requested'] for v in cached('balancer')['clients']] == [40]
    assert cached('pwm')['constraints']['max']['limiting'] is True
    assert cached('pwm')['constraints']['min'] == {'enabled': True, 'value': 5, 'limiting': False}

    # Readonly state may change between the two reads: retry until it did not
    for _ in range(20):
        await asyncio.sleep(0.05)
        await cmder.read_all_blocks(ReadMode.CHANGED)
        cmder.on_block_change = None
        full = await cmder.read_all_blocks()
        cmder.on_block_change = cache.on_block_change

        assert not cache.need_full
        assert [v.nid for v in full] == list(cache.entries)
        differences = {
            (block.type, key)
            for block in full
            for key in block.data.keys() | cache.entries[block.nid].data.keys()
            if key not in time_varying(block.type) and block.data.get(key) != cache.entries[block.nid].data.get(key)
        }
        if not differences:
            break

    assert differences == set()
    cmder.on_block_change = None


async def read_until(client: AsyncClient, sid: str, done: Callable[[dict], bool]) -> dict:
    """Reads a block until the firmware updated it"""
    for _ in range(20):
        block = (await client.post('/blocks/read', json={'id': sid})).json()
        if done(block['data']):
            return block
        await asyncio.sleep(0.05)
    raise AssertionError(f'{sid} was not updated: {block}')


async def test_broadcaster_tick(client: AsyncClient, s_publish: Mock, mocker: MockerFixture):
    """Broadcaster ticks against the simulator"""
    config = utils.get_config()
    config.full_read_interval = timedelta(seconds=10)
    s_read = mocker.spy(command.CV.get(), 'read_all_blocks')

    resp = await client.post(
        '/blocks/create', json={'id': 'pwm', 'type': 'ActuatorPwm', 'data': {'storedSetting': 80, 'period[s]': 2}}
    )
    assert resp.status_code == 201
    resp = await client.post(
        '/blocks/create',
        json={'id': 'sensor', 'type': 'TempSensorMock', 'data': {'setting[degC]': 20, 'connected': True}},
    )
    assert resp.status_code == 201
    await read_until(client, 'sensor', lambda data: data['value']['value'] == 20)

    bc = broadcast.Broadcaster()
    s_publish.reset_mock()
    with bc.hooked():
        await bc.tick()

        # A write, and the readonly state that follows from it
        resp = await client.post(
            '/blocks/patch', json={'id': 'sensor', 'type': 'TempSensorMock', 'data': {'setting[degC]': 25}}
        )
        assert resp.status_code == 200
        sensor = await read_until(client, 'sensor', lambda data: data['value']['value'] == 25)

        await bc.tick()

    def published(topic: str) -> list[dict]:
        return [c.args[1] for c in s_publish.call_args_list if c.args[0] == topic]

    assert [c.args[0] for c in s_read.call_args_list] == [ReadMode.DEFAULT, ReadMode.CHANGED]
    [full, changed] = published('brewcast/history/sparkey')
    [evt] = published('brewcast/state/sparkey')

    # The first tick is a full read, and publishes the state
    blocks = {v['id']: v for v in evt['data']['blocks']}
    assert blocks['pwm']['data']['period']['value'] == 2
    assert evt['data']['status']['connection_status'] == 'SYNCHRONIZED'

    # History has logged fields only
    assert set(full['data']) == set(blocks)
    assert set(full['data']['pwm']) == {'storedSetting', 'desiredSetting', 'setting', 'value'}
    for sid, logged in full['data'].items():
        block = blocks[sid]
        assert logged == codec.CV.get().logged_view(block['type'], block['data'], full=True)

    # CHANGED reads do not update skip_changed fields: they are only in history of full reads
    assert 'uptime[second]' in full['data']['SystemInfo']
    assert 'uptime[second]' not in changed['data']['SystemInfo']
    assert changed['data']['sensor']['value[degC]'] == 25

    # The patch has the complete blocks that changed, as a read has them.
    # The API published the write response before.
    [_, patch] = published('brewcast/state/sparkey/patch')
    assert [v['id'] for v in patch['data']['changed']] == ['sensor']
    assert patch['data']['changed'][0] == sensor


async def test_changed_revert(client: AsyncClient):
    """
    A CHANGED read leaves out a block whose covered state is what the previous CHANGED read sent,
    also if a full read in between showed another state.
    """
    state = state_machine.CV.get()
    cmder = command.CV.get()

    resp = await client.post(
        '/blocks/create',
        json={'id': 'sensor', 'type': 'TempSensorMock', 'data': {'setting[degC]': 20, 'connected': True}},
    )
    nid = resp.json()['nid']

    cache = broadcast.BlockCache()
    cache.reset(state.session)

    async def change(setting: float):
        """A change that the cache does not see: the sensor value follows its setting"""
        cmder.on_block_change = None
        resp = await client.post(
            '/blocks/patch', json={'id': 'sensor', 'type': 'TempSensorMock', 'data': {'setting[degC]': setting}}
        )
        assert resp.status_code == 200
        await read_until(client, 'sensor', lambda data: data['value']['value'] == setting)
        cmder.on_block_change = cache.on_block_change

    await change(20)
    await cmder.read_all_blocks()
    await cmder.read_all_blocks(ReadMode.CHANGED)

    await change(21)
    await cmder.read_all_blocks()
    assert cache.entries[nid].data['value']['value'] == 21

    await change(20)
    changed = await cmder.read_all_blocks(ReadMode.CHANGED)
    assert nid not in {v.nid for v in changed}
    assert cache.entries[nid].data['value']['value'] == 20
    cmder.on_block_change = None


async def test_changed_revert_written(client: AsyncClient):
    """
    A firmware-written stored field is in every CHANGED read of its block.
    If it returns to what the previous CHANGED read sent after a write response, the block is left out,
    and the cache restores it with the rest of what that read sent.
    """
    state = state_machine.CV.get()
    cmder = command.CV.get()
    api = spark_api.CV.get()

    await api.create_block(Block(id='sensor', type='TempSensorMock', data={'setting[degC]': 20, 'connected': True}))
    pair = await api.create_block(
        Block(
            id='pair',
            type='SetpointSensorPair',
            data={'sensorId<>': 'sensor', 'storedSetting[degC]': 21, 'enabled': True, 'settingMode': 'STORED'},
        )
    )
    await read_until(client, 'pair', lambda data: data['setting']['value'] == 21)

    cache = broadcast.BlockCache()
    cache.reset(state.session)
    cmder.on_block_change = cache.on_block_change

    await cmder.read_all_blocks()
    changed = await cmder.read_all_blocks(ReadMode.CHANGED)
    assert pair.nid in {v.nid for v in changed}

    # The response to an API write replaces the cached block
    await api.patch_block(Block(id='pair', type='SetpointSensorPair', data={'storedSetting[degC]': 25}))
    assert cache.entries[pair.nid].data['storedSetting']['value'] == 25

    # The firmware writes the stored setting back, as a Sequence does: the cache does not see it
    cmder.on_block_change = None
    await api.patch_block(Block(id='pair', type='SetpointSensorPair', data={'storedSetting[degC]': 21}))
    await read_until(client, 'pair', lambda data: data['setting']['value'] == 21)
    cmder.on_block_change = cache.on_block_change

    changed = await cmder.read_all_blocks(ReadMode.CHANGED)
    assert pair.nid not in {v.nid for v in changed}
    assert not cache.need_full

    cmder.on_block_change = None
    [full] = [v for v in await cmder.read_all_blocks() if v.nid == pair.nid]
    assert cache.entries[pair.nid].data == full.data
    assert full.data['storedSetting']['value'] == 21
