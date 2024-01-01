"""
Tests brewblox_devcon_spark.control
"""

import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import timedelta

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from pytest_mock import MockerFixture

from brewblox_devcon_spark import (codec, command, connection, const, control,
                                   datastore_blocks, datastore_settings,
                                   exceptions, mqtt, state_machine,
                                   synchronization, utils)
from brewblox_devcon_spark.connection import mock_connection
from brewblox_devcon_spark.models import (Block, BlockIdentity, ErrorCode,
                                          FirmwareBlock)

TESTED = control.__name__


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(mqtt.lifespan())
        await stack.enter_async_context(connection.lifespan())
        await stack.enter_async_context(synchronization.lifespan())
        yield


@pytest.fixture
def app() -> FastAPI:
    config = utils.get_config()
    config.mock = True

    mqtt.setup()
    state_machine.setup()
    datastore_settings.setup()
    datastore_blocks.setup()
    codec.setup()
    connection.setup()
    command.setup()
    control.setup()
    return FastAPI(lifespan=lifespan)


@pytest.fixture(autouse=True)
async def manager(manager: LifespanManager):
    yield manager


async def test_merge():
    assert control.merge(
        {},
        {'a': True}
    ) == {'a': True}
    assert control.merge(
        {'a': False},
        {'a': True}
    ) == {'a': True}
    assert control.merge(
        {'a': True},
        {'b': True}
    ) == {'a': True, 'b': True}
    assert control.merge(
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
async def test_validate_sid(sid: str):
    control.CV.get()._validate_sid(sid)


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
async def test_validate_sid_error(sid: str):
    with pytest.raises(exceptions.InvalidId):
        control.CV.get()._validate_sid(sid)


async def test_to_firmware_block():
    store = datastore_blocks.CV.get()
    ctrl = control.CV.get()

    store['alias', 123] = dict()
    store['4-2', 24] = dict()

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


async def test_to_block():
    store = datastore_blocks.CV.get()
    ctrl = control.CV.get()

    store['alias', 123] = dict()
    store['4-2', 24] = dict()

    assert ctrl._to_block(FirmwareBlock(nid=123, type='', data={})).id == 'alias'

    # Service ID not found: create placeholder
    generated = ctrl._to_block(FirmwareBlock(nid=456, type='', data={}))
    assert generated.id.startswith(const.GENERATED_ID_PREFIX)


async def test_resolve_data_ids():
    store = datastore_blocks.CV.get()
    ctrl = control.CV.get()

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

    data = create_data()
    control.resolve_data_ids(data, ctrl._find_nid)

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

    control.resolve_data_ids(data, ctrl._find_sid)
    assert data == create_data()

    control.resolve_data_ids(data, ctrl._find_nid)
    data['input<ProcessValueInterface>'] = 'eeney'
    with pytest.raises(exceptions.DecodeException):
        control.resolve_data_ids(data, ctrl._find_sid)


async def test_check_connection(mocker: MockerFixture):
    config = utils.get_config()
    sim = connection.CV.get()
    ctrl = control.CV.get()
    cmder = command.CV.get()

    s_noop = mocker.spy(cmder, 'noop')
    s_reset = mocker.spy(cmder, 'reset_connection')

    await ctrl.noop()
    await ctrl._check_connection()
    assert s_noop.await_count == 2
    assert s_reset.await_count == 0

    config.command_timeout = timedelta(milliseconds=100)
    with pytest.raises(exceptions.CommandTimeout):
        mock_connection.NEXT_ERROR = [None]
        await ctrl.noop()

    await asyncio.sleep(0.01)
    assert s_noop.await_count == 4

    with pytest.raises(exceptions.CommandTimeout):
        mock_connection.NEXT_ERROR = [None, ErrorCode.INSUFFICIENT_HEAP]
        await ctrl.noop()

    await asyncio.sleep(0.01)
    assert s_reset.await_count == 1

    # Should be a noop if not connected
    await sim.end()
    await ctrl._check_connection()
    assert s_noop.await_count == 6


async def test_start_update():
    state = state_machine.CV.get()
    ctrl = control.CV.get()

    await state.wait_synchronized()
    state.set_updating()

    with pytest.raises(exceptions.UpdateInProgress):
        await ctrl.read_all_blocks()
