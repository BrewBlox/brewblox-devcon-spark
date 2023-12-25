"""
Tests brewblox_devcon_spark.controller
"""

import asyncio

import pytest
from brewblox_service import scheduler

from brewblox_devcon_spark import (block_store, codec, commander, connection,
                                   const, controller, exceptions, global_store,
                                   service_store, state_machine,
                                   synchronization)
from brewblox_devcon_spark.connection import mock_connection
from brewblox_devcon_spark.models import (Block, BlockIdentity, ErrorCode,
                                          FirmwareBlock)

TESTED = controller.__name__


@pytest.fixture
def setup(app):
    state_machine.setup(app)
    scheduler.setup(app)
    codec.setup(app)
    connection.setup(app)
    commander.setup(app)
    block_store.setup(app)
    global_store.setup(app)
    service_store.setup(app)
    synchronization.setup(app)
    controller.setup(app)


@pytest.fixture
async def store(app, client):
    return block_store.fget(app)


async def test_merge():
    assert controller.merge(
        {},
        {'a': True}
    ) == {'a': True}
    assert controller.merge(
        {'a': False},
        {'a': True}
    ) == {'a': True}
    assert controller.merge(
        {'a': True},
        {'b': True}
    ) == {'a': True, 'b': True}
    assert controller.merge(
        {'nested': {'a': False, 'b': True}, 'second': {}},
        {'nested': {'a': True}, 'second': 'empty'}
    ) == {'nested': {'a': True, 'b': True}, 'second': 'empty'}


@pytest.mark.parametrize('sid', [
    'flabber',
    'FLABBER',
    'f(1)',
    'l12142|35234231',
    'word'*50,
])
async def test_validate_sid(sid, app, client):
    controller.fget(app)._validate_sid(sid)


@pytest.mark.parametrize('sid', [
    '1',
    '1adsjlfdsf',
    'pancakes[delicious]',
    '[',
    'f]abbergasted',
    '',
    'word'*51,
    'brackey><',
    'SystemInfo',
    'SparkPins',
    'a;ljfoihoewr*&(%&^&*%*&^(*&^(',
])
async def test_validate_sid_error(sid, app, client):
    with pytest.raises(exceptions.InvalidId):
        controller.fget(app)._validate_sid(sid)


async def test_to_firmware_block(app, client, store):
    store['alias', 123] = dict()
    store['4-2', 24] = dict()

    ctrl = controller.fget(app)

    assert ctrl._to_firmware_block(Block(id='alias', type='', data={})).nid == 123
    assert ctrl._to_firmware_block(Block(nid=840, type='', data={})).nid == 840

    assert ctrl._to_firmware_block_identity(BlockIdentity(id='alias')).nid == 123
    assert ctrl._to_firmware_block_identity(BlockIdentity(nid=840)).nid == 840

    # When both present, NID takes precedence
    assert ctrl._to_firmware_block(Block(id='alias', nid=444, type='', data={})).nid == 444

    with pytest.raises(exceptions.UnknownId):
        ctrl._to_firmware_block(Block(type='', data={}))

    with pytest.raises(exceptions.UnknownId):
        ctrl._to_firmware_block_identity(BlockIdentity())


async def test_to_block(app, client, store):
    store['alias', 123] = dict()
    store['4-2', 24] = dict()

    ctrl = controller.fget(app)

    assert ctrl._to_block(FirmwareBlock(nid=123, type='', data={})).id == 'alias'

    # Service ID not found: create placeholder
    generated = ctrl._to_block(FirmwareBlock(nid=456, type='', data={}))
    assert generated.id.startswith(const.GENERATED_ID_PREFIX)


async def test_resolve_data_ids(app, client, store):
    store['eeney', 9001] = dict()
    store['miney', 9002] = dict()
    store['moo', 9003] = dict()

    def create_data():
        return {
            'testval': 1,
            'input<ProcessValueInterface>': 'eeney',
            'output<ProcessValueInterface>': 'miney',
            'nested': {
                'flappy<>': 'moo',
                'meaning_of_life': 42,
                'mystery<EdgeCase>': None
            },
            'listed': [
                {'flappy<SetpointSensorPairInterface>': 'moo'}
            ],
            'metavalue': {
                '__bloxtype': 'Link',
                'id': 'eeney',
            },
        }

    ctrl = controller.fget(app)
    data = create_data()
    controller.resolve_data_ids(data, ctrl._find_nid)

    assert data == {
        'testval': 1,
        'input<ProcessValueInterface>': 9001,
        'output<ProcessValueInterface>': 9002,
        'nested': {
            'flappy<>': 9003,
            'meaning_of_life': 42,
            'mystery<EdgeCase>': 0,
        },
        'listed': [
            {'flappy<SetpointSensorPairInterface>': 9003},
        ],
        'metavalue': {
            '__bloxtype': 'Link',
            'id': 9001,
        },
    }

    controller.resolve_data_ids(data, ctrl._find_sid)
    assert data == create_data()

    controller.resolve_data_ids(data, ctrl._find_nid)
    data['input<ProcessValueInterface>'] = 'eeney'
    with pytest.raises(exceptions.DecodeException):
        controller.resolve_data_ids(data, ctrl._find_sid)


async def test_check_connection(app, client, mocker):
    sim = connection.fget(app)
    ctrl = controller.fget(app)
    cmder = commander.fget(app)

    s_noop = mocker.spy(cmder, 'noop')
    s_reconnect = mocker.spy(cmder, 'reset')

    await ctrl.noop()
    await ctrl._check_connection()
    assert s_noop.await_count == 2
    assert s_reconnect.await_count == 0

    cmder._timeout = 0.1
    with pytest.raises(exceptions.CommandTimeout):
        mock_connection.NEXT_ERROR = [None]
        await ctrl.noop()

    await asyncio.sleep(0.01)
    assert s_noop.await_count == 4

    with pytest.raises(exceptions.CommandTimeout):
        mock_connection.NEXT_ERROR = [None, ErrorCode.INSUFFICIENT_HEAP]
        await ctrl.noop()

    await asyncio.sleep(0.01)
    assert s_reconnect.await_count == 1

    # Should be a noop if not connected
    await sim.end()
    await ctrl._check_connection()
    assert s_noop.await_count == 6


async def test_start_update(app, client):
    await state_machine.wait_synchronized(app)
    state_machine.fget(app).set_updating()

    with pytest.raises(exceptions.UpdateInProgress):
        await controller.fget(app).read_all_blocks()
