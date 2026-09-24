import asyncio
import time
from collections.abc import Generator
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import timedelta
from unittest.mock import Mock

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from pytest_mock import MockerFixture

from brewblox_devcon_spark import (
    broadcast,
    codec,
    command,
    connection,
    datastore_blocks,
    datastore_settings,
    mqtt,
    spark_api,
    state_machine,
    synchronization,
    utils,
)
from brewblox_devcon_spark.broadcast import BlockCache, Broadcaster
from brewblox_devcon_spark.command import BlockChange
from brewblox_devcon_spark.connection import mock_connection
from brewblox_devcon_spark.models import (
    Block,
    BlockIdentity,
    DatastoreEvent,
    DecodedPayload,
    ErrorCode,
    FirmwareBlock,
    Opcode,
    ReadMode,
    StoredUnitSettingsValue,
)

TESTED = broadcast.__name__

STATE_TOPIC = 'brewcast/state/sparkey'
PATCH_TOPIC = 'brewcast/state/sparkey/patch'
HISTORY_TOPIC = 'brewcast/history/sparkey'

SYSTEM_IDS = {'SystemInfo', 'WiFiSettings', 'DisplaySettings', 'SparkPins'}


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
    config.broadcast_interval = timedelta(milliseconds=10)
    config.full_read_interval = timedelta(seconds=10)
    config.broadcast_timeout = timedelta(milliseconds=100)

    mqtt.setup()
    state_machine.setup()
    datastore_settings.setup()
    datastore_blocks.setup()
    codec.setup()
    connection.setup()
    command.setup()
    spark_api.setup()
    return FastAPI(lifespan=lifespan)


@pytest.fixture(autouse=True)
async def manager(manager: LifespanManager):
    return manager


@pytest.fixture(autouse=True)
async def synchronized(manager: LifespanManager):
    await state_machine.CV.get().wait_synchronized()


@pytest.fixture
def s_publish(mocker: MockerFixture) -> Mock:
    return mocker.spy(mqtt.CV.get(), 'publish')


@pytest.fixture
def s_read(mocker: MockerFixture) -> Mock:
    return mocker.spy(command.CV.get(), 'read_all_blocks')


@pytest.fixture
def bc(synchronized) -> Generator[Broadcaster, None, None]:
    b = Broadcaster()
    with b.hooked():
        yield b


def published(s_publish: Mock, topic: str) -> list[dict]:
    return [c.args[1] for c in s_publish.call_args_list if c.args[0] == topic]


def read_modes(s_read: Mock) -> list[ReadMode]:
    return [c.args[0] for c in s_read.call_args_list]


def mock_impl() -> mock_connection.MockConnection:
    return connection.CV.get()._impl


def firmware_block(nid: int, block_type: str, data: dict, mode: ReadMode = ReadMode.DEFAULT) -> FirmwareBlock:
    """Block data as the controller would send it"""
    c = codec.CV.get()
    encoded = c.encode_payload(DecodedPayload(blockId=nid, blockType=block_type, content=data), filter_values=False)
    decoded = c.decode_payload(encoded, mode=mode)
    return FirmwareBlock(nid=nid, type=decoded.blockType, data=decoded.content)


def sensor(nid: int, value: float, mode: ReadMode = ReadMode.DEFAULT) -> FirmwareBlock:
    data = {'value': value} if mode == ReadMode.CHANGED else {'value': value, 'setting': value, 'connected': True}
    return firmware_block(nid, 'TempSensorMock', data, mode)


def read_all(seq: int, *blocks: FirmwareBlock, mode=ReadMode.DEFAULT, error: str | None = None) -> BlockChange:
    return BlockChange(seq, 1, Opcode.BLOCK_READ_ALL, mode, list(blocks), error=error)


def cached_value(cache: BlockCache, nid: int) -> float:
    return cache.entries[nid].data['value']['value']


@pytest.fixture
def cache(synchronized) -> BlockCache:
    c = BlockCache()
    c.reset(1)
    return c


async def create_sensor(api: spark_api.SparkApi, sid: str = 'sensor') -> Block:
    return await api.create_block(
        Block(id=sid, type='TempSensorMock', data={'setting[degC]': 20, 'connected': True}),
    )


def test_next_deadline():
    # On time: the next deadline is one interval later
    assert broadcast.next_deadline(10, 10.2, 1) == 11
    assert broadcast.next_deadline(10, 11, 1) == 11

    # Late: missed deadlines are skipped
    assert broadcast.next_deadline(10, 11.5, 1) == 12
    assert broadcast.next_deadline(10, 13.1, 1) == 14


async def test_cache_full_read(cache: BlockCache):
    cache.request_full(3)

    # An older full read does not satisfy a newer need
    cache.on_block_change(read_all(2, sensor(100, 20), sensor(101, 20)))
    assert cache.need_full
    assert list(cache.entries) == [100, 101]
    assert cache.take_dirty() == [100, 101]
    assert cache.take_dirty() == []

    cache.on_block_change(read_all(4, sensor(101, 21), sensor(102, 20)))
    assert not cache.need_full
    assert list(cache.entries) == [101, 102]
    assert cached_value(cache, 101) == 21
    assert cache.take_dirty() == [101, 102]

    # Unchanged blocks are not dirty
    cache.on_block_change(read_all(5, sensor(101, 21), sensor(102, 22)))
    assert cache.take_dirty() == [102]
    assert cache.entries[101].seq == 5

    # Cached data is a copy: the caller may modify its blocks
    block = sensor(103, 20)
    cache.on_block_change(read_all(6, block))
    block.data['value']['value'] = 30
    assert cached_value(cache, 103) == 20


async def test_cache_out_of_order(cache: BlockCache):
    cache.on_block_change(read_all(1, sensor(100, 20), sensor(101, 20)))

    # A write, a delete and a create, sent after a full read that is handled last
    cache.on_block_change(BlockChange(3, 1, Opcode.BLOCK_WRITE, blocks=[sensor(100, 25)]))
    cache.on_block_change(BlockChange(4, 1, Opcode.BLOCK_DELETE, nid=101))
    cache.on_block_change(BlockChange(5, 1, Opcode.BLOCK_CREATE, blocks=[sensor(102, 25)]))
    cache.on_block_change(read_all(2, sensor(100, 21), sensor(101, 21)))

    # Newer entries are kept, the deleted block does not come back, and the new block is not removed
    assert list(cache.entries) == [100, 102]
    assert cached_value(cache, 100) == 25
    assert not cache.need_full

    # A CHANGED read sent before the write is not merged
    cache.on_block_change(read_all(2, sensor(100, 22, ReadMode.CHANGED), mode=ReadMode.CHANGED))
    assert cached_value(cache, 100) == 25
    assert cache.entries[100].seq == 3
    assert not cache.need_full

    # Nor is one of the deleted block
    cache.on_block_change(read_all(2, sensor(101, 22, ReadMode.CHANGED), mode=ReadMode.CHANGED))
    assert 101 not in cache.entries
    assert not cache.need_full

    # A delete sent before the create is not applied
    cache.on_block_change(BlockChange(4, 1, Opcode.BLOCK_DELETE, nid=102))
    assert 102 in cache.entries

    # A write sent before the delete is not applied
    cache.on_block_change(BlockChange(3, 1, Opcode.BLOCK_WRITE, blocks=[sensor(101, 25)]))
    assert 101 not in cache.entries
    assert not cache.need_full

    # A write handled after a newer read: a CHANGED read would not have what the write stored
    cache.on_block_change(read_all(7, sensor(100, 26, ReadMode.CHANGED), mode=ReadMode.CHANGED))
    cache.on_block_change(BlockChange(6, 1, Opcode.BLOCK_WRITE, blocks=[sensor(100, 25)]))
    assert cached_value(cache, 100) == 26
    assert cache.need_full

    # A full read sent after the delete finds the block created again
    cache.on_block_change(read_all(8, sensor(100, 26), sensor(101, 20), sensor(102, 20)))
    assert list(cache.entries) == [100, 101, 102]
    assert not cache.need_full

    # Deleting a block that is not cached leaves a tombstone
    cache.on_block_change(BlockChange(9, 1, Opcode.BLOCK_DELETE, nid=200))
    cache.on_block_change(read_all(8, sensor(200, 20)))
    assert 200 not in cache.entries

    # Tombstones go once a full read sent after the delete is applied
    assert cache._tombstones
    cache.on_block_change(read_all(10, sensor(100, 26)))
    assert cache._tombstones == {}


async def test_cache_changed_read(cache: BlockCache):
    cache.on_block_change(read_all(1, sensor(100, 20), sensor(101, 20)))
    cache.take_dirty()

    cache.on_block_change(
        read_all(2, sensor(100, 21, ReadMode.CHANGED), sensor(101, 20, ReadMode.CHANGED), mode=ReadMode.CHANGED)
    )
    assert cached_value(cache, 100) == 21
    assert cache.entries[100].data['setting']['value'] == 20  # Kept
    assert cache.entries[101].seq == 2
    assert cache.take_dirty() == [100]  # Only merges that changed something
    assert not cache.need_full

    # A block the cache does not know
    cache.on_block_change(read_all(3, sensor(102, 20, ReadMode.CHANGED), mode=ReadMode.CHANGED))
    assert cache.need_full
    assert 102 not in cache.entries

    cache.on_block_change(read_all(4, sensor(100, 21), sensor(101, 20)))
    assert not cache.need_full

    # A block with the same nid, but another type
    cache.on_block_change(
        read_all(5, firmware_block(101, 'TempSensorExternal', {}, ReadMode.CHANGED), mode=ReadMode.CHANGED)
    )
    assert cache.need_full
    assert cache.entries[101].type == 'TempSensorMock'

    cache.on_block_change(read_all(6, sensor(100, 21), sensor(101, 20)))

    # A read that failed halfway: the blocks before the error are merged
    cache.on_block_change(
        read_all(7, sensor(100, 22, ReadMode.CHANGED), mode=ReadMode.CHANGED, error='INSUFFICIENT_HEAP')
    )
    assert cached_value(cache, 100) == 22
    assert cache.need_full


async def test_cache_reader_view(cache: BlockCache):
    """
    A CHANGED read leaves out the blocks whose CHANGED payload is what the controller last sent in a CHANGED read:
    the covered values, and the firmware-written stored fields it sends in every CHANGED read.
    Full reads and write responses may have replaced that state in the cache since.
    """
    changed = ReadMode.CHANGED
    cache.on_block_change(read_all(1, sensor(100, 20), sensor(101, 20), sensor(102, 20)))
    cache.on_block_change(
        read_all(
            2,
            sensor(100, 20, changed),
            firmware_block(101, 'TempSensorMock', {'value': 20, 'setting': 20}, changed),  # Firmware-written
            sensor(102, 20, changed),
            mode=changed,
        )
    )

    # The values change, and are read in full or written
    cache.on_block_change(read_all(3, sensor(100, 21), sensor(101, 20), sensor(102, 21)))
    cache.on_block_change(BlockChange(4, 1, Opcode.BLOCK_WRITE, blocks=[sensor(101, 22)]))
    cache.take_dirty()

    # Two return to what the CHANGED read sent, and the next one leaves them out
    cache.on_block_change(read_all(5, sensor(102, 21, changed), mode=changed))
    assert cached_value(cache, 100) == 20
    assert cached_value(cache, 101) == 20
    assert cache.entries[101].data['setting']['value'] == 20  # Firmware-written: part of the payload
    assert cached_value(cache, 102) == 21
    assert cache.entries[100].seq == 5
    assert cache.take_dirty() == [100, 101]
    assert not cache.need_full

    # Blocks that were not replaced since are left alone
    cache.on_block_change(read_all(6, mode=changed))
    assert cache.entries[100].seq == 5
    assert cache.take_dirty() == []

    # So are blocks replaced by a response to a later request
    cache.on_block_change(BlockChange(8, 1, Opcode.BLOCK_WRITE, blocks=[sensor(100, 23)]))
    cache.on_block_change(read_all(7, mode=changed))
    assert cached_value(cache, 100) == 23

    # A read that failed may have left out blocks it did not reach
    cache.on_block_change(read_all(9, mode=changed, error='INSUFFICIENT_HEAP'))
    assert cached_value(cache, 100) == 23

    # The views of blocks that are gone are dropped
    cache.on_block_change(read_all(10, sensor(100, 20, changed), sensor(101, 20, changed), mode=changed))
    assert set(cache._views) == {100, 101}
    cache.on_block_change(read_all(11, sensor(100, 20)))
    assert set(cache._views) == {100}

    # Stub types are replaced, also by their view
    cache.on_block_change(
        read_all(12, sensor(100, 20), FirmwareBlock(nid=103, type='ErrorObject', data={'error': 'a'}))
    )
    cache.on_block_change(read_all(13, FirmwareBlock(nid=103, type='ErrorObject', data={'error': 'b'}), mode=changed))
    assert cache.entries[103].data == {'error': 'b'}
    assert set(cache._views) == {100, 103}
    cache.on_block_change(
        read_all(14, sensor(100, 20), FirmwareBlock(nid=103, type='ErrorObject', data={'error': 'c'}))
    )
    cache.on_block_change(read_all(15, mode=changed))
    assert cache.entries[103].data == {'error': 'b'}


@pytest.mark.parametrize(
    'change',
    [
        # The controller may have sent blocks that the cache did not see
        read_all(3, mode=ReadMode.CHANGED, error='CommandTimeout'),
        BlockChange(3, 1, None, error='late response'),
        # The block is gone
        BlockChange(3, 1, Opcode.BLOCK_DELETE, nid=100),
    ],
)
async def test_cache_reader_view_dropped(cache: BlockCache, change: BlockChange):
    changed = ReadMode.CHANGED
    cache.on_block_change(read_all(1, sensor(100, 20)))
    cache.on_block_change(read_all(2, sensor(100, 20, changed), mode=changed))

    cache.on_block_change(change)
    cache.on_block_change(read_all(4, sensor(100, 21)))
    cache.on_block_change(read_all(5, mode=changed))
    assert cached_value(cache, 100) == 21


async def test_cache_reader_view_type(cache: BlockCache):
    """A CHANGED read of a block the cache has with another type"""
    changed = ReadMode.CHANGED
    cache.on_block_change(read_all(1, sensor(100, 20)))
    cache.on_block_change(read_all(2, firmware_block(100, 'TempSensorExternal', {}, changed), mode=changed))
    assert cache.need_full

    cache.on_block_change(read_all(3, sensor(100, 21)))
    cache.on_block_change(read_all(4, mode=changed))
    assert cached_value(cache, 100) == 21
    assert not cache.need_full


async def test_cache_need_full_read(cache: BlockCache, mocker: MockerFixture):
    cache.on_block_change(read_all(1, sensor(100, 20)))

    mocker.patch.object(cache.codec, 'merge_changed', side_effect=codec.NeedFullRead('not cached'))
    cache.on_block_change(read_all(2, sensor(100, 21, ReadMode.CHANGED), mode=ReadMode.CHANGED))
    assert cache.need_full
    assert cache.entries[100].seq == 1


async def test_cache_errors(cache: BlockCache, mocker: MockerFixture):
    cache.on_block_change(read_all(1, sensor(100, 20), sensor(101, 20)))
    assert not cache.need_full

    # A full read that failed halfway does not remove blocks
    cache.on_block_change(read_all(2, sensor(100, 21), error='INSUFFICIENT_HEAP'))
    assert cache.need_full
    assert list(cache.entries) == [100, 101]
    assert cached_value(cache, 100) == 20

    cache.on_block_change(read_all(3, sensor(100, 20), sensor(101, 20)))
    assert not cache.need_full

    # A failed write may have been applied
    cache.on_block_change(BlockChange(4, 1, Opcode.BLOCK_WRITE, nid=100, error='CommandTimeout'))
    assert cache.need_full
    assert cached_value(cache, 100) == 20

    cache.on_block_change(read_all(5, sensor(100, 20), sensor(101, 20)))

    # A bug in applying a change
    mocker.patch.object(cache, '_apply_full', side_effect=RuntimeError('bug'))
    with pytest.raises(RuntimeError):
        cache.on_block_change(read_all(6, sensor(100, 20), sensor(101, 20)))
    assert cache.need_full


@pytest.mark.parametrize(
    'change',
    [
        BlockChange(2, 1, Opcode.CLEAR_BLOCKS),
        BlockChange(2, 1, Opcode.BLOCK_DISCOVER),
        BlockChange(2, 1, None, error='late response'),
        BlockChange(2, 1, None, error='unsolicited handshake'),
    ],
)
async def test_cache_untracked_changes(cache: BlockCache, change: BlockChange):
    cache.on_block_change(read_all(1, sensor(100, 20)))
    assert not cache.need_full

    cache.on_block_change(change)
    assert cache.need_full


async def test_cache_ignored(cache: BlockCache):
    cache.on_block_change(read_all(1, sensor(100, 20)))

    # Stored reads only have persistent fields
    cache.on_block_change(read_all(2, sensor(100, 21), mode=ReadMode.STORED))
    cache.on_block_change(read_all(3, mode=ReadMode.STORED, error='INSUFFICIENT_HEAP'))

    # Requests from another session
    cache.on_block_change(BlockChange(4, 2, Opcode.CLEAR_BLOCKS))

    assert cached_value(cache, 100) == 20
    assert not cache.need_full

    # Nothing is applied before the cache has a session
    cache.reset(None)
    cache.on_block_change(read_all(5, sensor(100, 20)))
    assert cache.entries == {}
    assert cache.need_full


async def test_cache_units(cache: BlockCache):
    """
    Changes are decoded in the units of the moment.
    Only full reads can switch the cache to other units.
    """
    converter = codec.unit_conversion.CV.get()
    changed = ReadMode.CHANGED
    cache.on_block_change(read_all(1, sensor(100, 20), sensor(101, 20)))
    cache.on_block_change(read_all(2, sensor(100, 20, changed), sensor(101, 20, changed), mode=changed))
    cache.take_dirty()

    converter.temperature = 'degF'
    cache.on_block_change(read_all(3, sensor(100, 70, changed), mode=changed))
    cache.on_block_change(BlockChange(5, 1, Opcode.BLOCK_WRITE, blocks=[sensor(101, 70)]))
    assert cache.need_full
    assert cache.take_dirty() == []
    assert cache.entries[100].data['value']['unit'] == 'degC'
    assert cache.entries[101].data['value']['unit'] == 'degC'

    # A full read sent before the write does not satisfy the need
    cache.on_block_change(read_all(4, sensor(100, 70), sensor(101, 71)))
    assert cache.need_full
    assert cache.entries[100].data['value']['unit'] == 'degF'

    cache.on_block_change(read_all(6, sensor(100, 70), sensor(101, 71)))
    assert not cache.need_full

    # What CHANGED reads sent in other units is not merged into the cache later
    cache.on_block_change(read_all(7, mode=changed))
    assert cached_value(cache, 100) == pytest.approx(70, abs=0.01)
    assert cached_value(cache, 101) == pytest.approx(71, abs=0.01)

    cache.on_block_change(read_all(8, sensor(100, 71, changed), mode=changed))
    converter.temperature = 'degC'
    cache.on_block_change(read_all(9, sensor(100, 20), sensor(101, 21)))
    cache.on_block_change(read_all(10, mode=changed))
    assert cache.entries[100].data['value'] == {'__bloxtype': 'Quantity', 'unit': 'degC', 'value': 20, 'readonly': True}

    # Nor if the units change back before the next full read
    cache.on_block_change(read_all(11, sensor(100, 21, changed), mode=changed))
    converter.temperature = 'degF'
    cache.on_block_change(read_all(12, sensor(100, 70, changed), mode=changed))
    converter.temperature = 'degC'
    cache.on_block_change(read_all(13, sensor(100, 20), sensor(101, 21)))
    cache.on_block_change(read_all(14, mode=changed))
    assert cached_value(cache, 100) == 20

    # A full read in other units, while a newer write response is cached
    cache.on_block_change(BlockChange(16, 1, Opcode.BLOCK_WRITE, blocks=[sensor(101, 22)]))
    converter.temperature = 'degF'
    cache.on_block_change(read_all(15, sensor(100, 70), sensor(101, 71)))
    assert cache.entries[101].data['value']['unit'] == 'degC'
    assert cache.need_full
    cache.on_block_change(read_all(17, sensor(100, 70), sensor(101, 72)))
    assert cache.entries[101].data['value']['unit'] == 'degF'
    assert not cache.need_full


async def test_unsynchronized(bc: Broadcaster, s_publish: Mock, s_read: Mock):
    state = state_machine.CV.get()

    await bc.tick()
    assert bc.cache.entries

    state._synchronized_ev.clear()
    s_publish.reset_mock()

    # Only the status is published, and the cache is reset
    bc._last_full = None
    await bc.tick()
    assert bc.cache.entries == {}
    assert bc.cache.session is None
    assert s_read.call_count == 1

    [evt] = published(s_publish, STATE_TOPIC)
    assert evt['data']['blocks'] == []
    assert evt['data']['status']['connection_status'] == 'SYNCHRONIZED'
    assert s_publish.call_args.kwargs == {'retain': True}

    # Status is published on the full read cadence
    s_publish.reset_mock()
    await bc.tick()
    assert s_publish.call_count == 0

    bc._last_full -= 10
    await bc.tick()
    assert s_publish.call_count == 1

    # Updating counts as not synchronized
    state._synchronized_ev.set()
    state.set_updating()
    bc._last_full -= 10
    await bc.tick()
    assert s_publish.call_count == 2
    assert published(s_publish, STATE_TOPIC)[-1]['data']['status']['connection_status'] == 'UPDATING'
    assert s_read.call_count == 1


async def test_first_tick(bc: Broadcaster, s_publish: Mock, s_read: Mock):
    await bc.tick()

    assert read_modes(s_read) == [ReadMode.DEFAULT]
    assert [c.args[0] for c in s_publish.call_args_list] == [HISTORY_TOPIC, STATE_TOPIC]

    [history] = published(s_publish, HISTORY_TOPIC)
    assert history['key'] == 'sparkey'
    assert set(history['data']) == SYSTEM_IDS

    [evt] = published(s_publish, STATE_TOPIC)
    assert {v['id'] for v in evt['data']['blocks']} == SYSTEM_IDS
    assert evt['data']['status']['connection_status'] == 'SYNCHRONIZED'
    assert s_publish.call_args.kwargs == {'retain': True}


async def test_changed_tick(bc: Broadcaster, s_publish: Mock, s_read: Mock):
    api = spark_api.CV.get()
    created = await create_sensor(api)

    await bc.tick()
    s_publish.reset_mock()

    # Nothing changed: only history
    await bc.tick()
    assert read_modes(s_read) == [ReadMode.DEFAULT, ReadMode.CHANGED]
    assert [c.args[0] for c in s_publish.call_args_list] == [HISTORY_TOPIC]
    s_publish.reset_mock()

    # A change that only a CHANGED read shows
    mock_impl()._blocks[created.nid].message.value = 21 * 4096
    await bc.tick()
    assert read_modes(s_read)[-1] == ReadMode.CHANGED
    assert [c.args[0] for c in s_publish.call_args_list] == [HISTORY_TOPIC, PATCH_TOPIC]

    [history] = published(s_publish, HISTORY_TOPIC)
    assert history['data']['sensor'] == {'value[degC]': 21, 'connected': True}

    # The patch has the complete block, as a read has it
    [patch] = published(s_publish, PATCH_TOPIC)
    assert s_publish.call_args.kwargs == {}
    [changed] = patch['data']['changed']
    assert changed == (await api.read_block(BlockIdentity(id='sensor'))).model_dump(mode='json')
    assert patch['data']['deleted'] == []

    # Blocks written through the API are in the next patch, also if the CHANGED read of the tick leaves them out.
    # The firmware leaves out a block after a write that only changed stored fields.
    # Here, a CHANGED read before the tick sends it.
    s_publish.reset_mock()
    await api.write_block(Block(id='sensor', type='TempSensorMock', data={'connected': False}))
    assert created.nid in {v.nid for v in await bc.cmder.read_all_blocks(ReadMode.CHANGED)}
    await bc.tick()
    assert read_modes(s_read)[-1] == ReadMode.CHANGED
    assert created.nid not in {v.nid for v in s_read.spy_return}
    [patch] = published(s_publish, PATCH_TOPIC)
    assert [v['id'] for v in patch['data']['changed']] == ['sensor']
    assert patch['data']['changed'][0]['data']['connected'] is False

    # Unchanged blocks are merged, but not published
    s_publish.reset_mock()
    mock_impl()._changed_sent.clear()
    await bc.tick()
    assert read_modes(s_read)[-1] == ReadMode.CHANGED
    assert [c.args[0] for c in s_publish.call_args_list] == [HISTORY_TOPIC]


async def test_changed_revert(bc: Broadcaster, s_publish: Mock):
    """A value changes before a full read, and returns to what the previous CHANGED read sent"""
    api = spark_api.CV.get()
    created = await create_sensor(api)
    message = mock_impl()._blocks[created.nid].message
    message.value = 20 * 4096

    await bc.tick()
    await bc.tick()  # CHANGED: 20

    message.value = 21 * 4096
    bc._last_full = None
    await bc.tick()  # Full: 21

    message.value = 20 * 4096
    s_publish.reset_mock()
    await bc.tick()  # CHANGED: nothing

    [history] = published(s_publish, HISTORY_TOPIC)
    assert history['data']['sensor']['value[degC]'] == 20
    [patch] = published(s_publish, PATCH_TOPIC)
    [changed] = patch['data']['changed']
    assert changed == (await api.read_block(BlockIdentity(id='sensor'))).model_dump(mode='json')


async def test_changed_revert_written(bc: Broadcaster):
    """
    A firmware-written stored field returns to what the previous CHANGED read sent, after a write response.
    The CHANGED read leaves the block out: its view restores the whole block.
    """
    state = state_machine.CV.get()
    api = spark_api.CV.get()
    cmder = command.CV.get()
    cache = bc.cache
    cache.reset(state.session)

    created = await create_sensor(api)
    message = mock_impl()._blocks[created.nid].message

    await cmder.read_all_blocks()
    await cmder.read_all_blocks(ReadMode.CHANGED)

    # A write through the API: the response replaces the cached block
    await api.patch_block(Block(id='sensor', type='TempSensorMock', data={'setting[degC]': 25}))
    assert cache.entries[created.nid].data['setting']['value'] == 25

    # The firmware writes the setting back: no response reaches the cache
    message.setting = 20 * 4096
    changed = await cmder.read_all_blocks(ReadMode.CHANGED)
    assert created.nid not in {v.nid for v in changed}
    assert not cache.need_full

    cmder.on_block_change = None
    [full] = [v for v in await cmder.read_all_blocks() if v.nid == created.nid]
    assert cache.entries[created.nid].data == full.data
    assert full.data['setting']['value'] == 20


async def test_links(bc: Broadcaster, s_publish: Mock):
    """Published blocks have string IDs, and publishing does not change the cache"""
    api = spark_api.CV.get()
    created = await create_sensor(api)
    pair = await api.create_block(Block(id='pair', type='SetpointSensorPair', data={'sensorId<>': 'sensor'}))

    for _ in range(2):
        await bc.tick()
        bc._last_full = None

    [_, evt] = published(s_publish, STATE_TOPIC)
    [published_pair] = [v for v in evt['data']['blocks'] if v['id'] == 'pair']
    assert published_pair['data']['sensorId']['id'] == 'sensor'
    assert bc.cache.entries[pair.nid].data['sensorId']['id'] == created.nid


async def test_full_interval(bc: Broadcaster, s_publish: Mock, s_read: Mock):
    config = utils.get_config()

    await bc.tick()
    await bc.tick()
    assert read_modes(s_read) == [ReadMode.DEFAULT, ReadMode.CHANGED]

    # Ticks start a little late: a full read is due half a tick early
    interval = config.broadcast_interval.total_seconds()
    full_interval = config.full_read_interval.total_seconds()
    last_full = bc._last_full
    bc._last_full = 100.0
    assert bc._full_due(100.0 + full_interval - interval / 4)
    assert not bc._full_due(100.0 + full_interval - interval)

    # A full read publishes the state
    bc._last_full = last_full - full_interval
    s_publish.reset_mock()
    await bc.tick()
    assert read_modes(s_read)[-1] == ReadMode.DEFAULT
    assert len(published(s_publish, STATE_TOPIC)) == 1

    # full_read_interval <= broadcast_interval: every read is a full read
    config.full_read_interval = config.broadcast_interval
    await bc.tick()
    await bc.tick()
    assert read_modes(s_read)[-2:] == [ReadMode.DEFAULT, ReadMode.DEFAULT]
    assert len(published(s_publish, STATE_TOPIC)) == 3


async def test_history(bc: Broadcaster, s_publish: Mock):
    await bc.tick()
    await bc.tick()

    [full, changed] = published(s_publish, HISTORY_TOPIC)

    # Only logged fields
    assert 'deviceId' not in full['data']['SystemInfo']
    assert full['data']['DisplaySettings'] == {}

    # skip_changed fields are only in history after a full read: CHANGED reads do not update them
    assert 'uptime[second]' in full['data']['SystemInfo']
    assert 'uptime[second]' not in changed['data']['SystemInfo']


async def test_read_error(bc: Broadcaster, s_publish: Mock, s_read: Mock):
    await bc.tick()
    s_publish.reset_mock()

    # Error response
    mock_connection.NEXT_ERROR.append(ErrorCode.UNKNOWN_ERROR)
    await bc.tick()
    assert s_publish.call_count == 0
    assert bc.cache.need_full

    # No response
    mock_connection.NEXT_ERROR.append(None)
    await bc.tick()
    assert s_publish.call_count == 0

    await bc.tick()
    assert read_modes(s_read) == [ReadMode.DEFAULT, ReadMode.CHANGED, ReadMode.DEFAULT, ReadMode.DEFAULT]
    assert len(published(s_publish, STATE_TOPIC)) == 1
    assert not bc.cache.need_full

    # Also when no response reached the cache
    bc.cmder.on_block_change = None
    mock_connection.NEXT_ERROR.append(ErrorCode.UNKNOWN_ERROR)
    await bc.tick()
    assert bc.cache.need_full


async def test_read_timeout(bc: Broadcaster, mocker: MockerFixture):
    """A controller that stops answering is reconnected, as after an API request that timed out"""
    config = utils.get_config()
    config.command_timeout = timedelta(milliseconds=100)
    state = state_machine.CV.get()
    s_check = mocker.spy(bc.api, 'check_connection')
    s_reset = mocker.spy(bc.cmder, 'reset_connection')

    await bc.tick()

    # An error response is an answer
    mock_connection.NEXT_ERROR.append(ErrorCode.UNKNOWN_ERROR)
    await bc.tick()
    await asyncio.sleep(0.01)
    assert s_check.await_count == 0

    # The controller never answers: not the read, and not the noop of the connection check
    session = state.session
    mock_connection.NEXT_ERROR.extend([None, None])
    await bc.tick()
    assert bc.cache.need_full
    assert s_check.call_count == 1
    await asyncio.wait_for(state.wait_disconnected(), timeout=1)
    assert s_reset.await_count == 1

    await asyncio.wait_for(state.wait_synchronized(), timeout=1)
    assert state.session == session + 1


async def test_merge_error(bc: Broadcaster, s_publish: Mock, s_read: Mock, mocker: MockerFixture):
    await bc.tick()
    s_publish.reset_mock()

    mocker.patch.object(bc.codec, 'merge_changed', side_effect=codec.NeedFullRead('not cached'))
    await bc.tick()
    assert read_modes(s_read)[-1] == ReadMode.CHANGED
    assert s_publish.call_count == 0

    await bc.tick()
    assert read_modes(s_read)[-1] == ReadMode.DEFAULT
    assert len(published(s_publish, STATE_TOPIC)) == 1


async def test_unknown_block(bc: Broadcaster, s_publish: Mock, s_read: Mock):
    api = spark_api.CV.get()
    await bc.tick()
    s_publish.reset_mock()

    # Created without the cache seeing it
    bc.cmder.on_block_change = None
    await create_sensor(api)
    bc.cmder.on_block_change = bc.cache.on_block_change

    await bc.tick()
    assert read_modes(s_read)[-1] == ReadMode.CHANGED
    assert s_publish.call_count == 0

    await bc.tick()
    assert read_modes(s_read)[-1] == ReadMode.DEFAULT
    [evt] = published(s_publish, STATE_TOPIC)
    assert 'sensor' in {v['id'] for v in evt['data']['blocks']}


async def test_session_change(bc: Broadcaster, s_publish: Mock, s_read: Mock, mocker: MockerFixture):
    state = state_machine.CV.get()
    await bc.tick()

    # A reconnect
    state.session += 1
    await bc.tick()
    assert read_modes(s_read) == [ReadMode.DEFAULT, ReadMode.DEFAULT]
    assert bc.cache.session == state.session
    assert len(published(s_publish, STATE_TOPIC)) == 2

    # A reconnect during the read
    read_all_blocks = bc.cmder.read_all_blocks

    async def reconnecting_read(*args, **kwargs):
        blocks = await read_all_blocks(*args, **kwargs)
        state.session += 1
        return blocks

    mocker.patch.object(bc.cmder, 'read_all_blocks', reconnecting_read)
    s_publish.reset_mock()
    await bc.tick()
    assert s_publish.call_count == 0


async def test_unit_change(bc: Broadcaster, s_publish: Mock, s_read: Mock):
    settings = datastore_settings.CV.get()
    api = spark_api.CV.get()
    created = await create_sensor(api)

    def published_sensor() -> dict:
        [evt] = published(s_publish, STATE_TOPIC)[-1:]
        return next(v for v in evt['data']['blocks'] if v['id'] == 'sensor')

    await bc.tick()
    await bc.tick()
    assert read_modes(s_read) == [ReadMode.DEFAULT, ReadMode.CHANGED]

    await settings.on_global_store_event(DatastoreEvent(changed=[StoredUnitSettingsValue(temperature='degF')]))
    await bc.tick()
    assert read_modes(s_read)[-1] == ReadMode.DEFAULT
    assert published_sensor()['data']['value']['unit'] == 'degF'

    [evt] = published(s_publish, STATE_TOPIC)[-1:]
    [sysinfo] = [v for v in evt['data']['blocks'] if v['id'] == 'SystemInfo']
    assert sysinfo['data']['tempUnit'] == 'TEMP_FAHRENHEIT'

    # Synchronization sets the units of the service, and then writes them to the controller.
    # A tick in between reads the changes in the new units.
    codec.unit_conversion.CV.get().temperature = 'degC'
    mock_impl()._blocks[created.nid].message.value = 21 * 4096
    s_publish.reset_mock()
    await bc.tick()
    assert read_modes(s_read)[-1] == ReadMode.CHANGED
    assert s_publish.call_count == 0

    await bc.tick()
    assert read_modes(s_read)[-1] == ReadMode.DEFAULT
    assert published_sensor()['data']['value'] == {
        '__bloxtype': 'Quantity',
        'unit': 'degC',
        'value': 21,
        'readonly': True,
    }
    assert published_sensor()['data']['setting']['unit'] == 'degC'


async def test_repeat(bc: Broadcaster, mocker: MockerFixture):
    config = utils.get_config()
    interval = config.broadcast_interval.total_seconds()
    tick_duration = 0.004
    loop = asyncio.get_running_loop()
    tick_starts = []

    def slow_tick():
        tick_starts.append(loop.time())
        time.sleep(tick_duration)
        raise RuntimeError('tick failed')

    s_tick = mocker.patch.object(bc, 'tick', autospec=True)
    s_tick.side_effect = slow_tick
    s_deadline = mocker.spy(broadcast, 'next_deadline')
    m_asyncio = mocker.patch.object(broadcast, 'asyncio', wraps=asyncio)

    # Errors do not stop the loop
    async with utils.task_context(bc.repeat()):
        await asyncio.sleep(0.05)
    assert s_tick.await_count >= 2

    # Ticks are scheduled by deadline: each one interval after the previous deadline.
    # The time a tick takes is not added to the interval: the loop sleeps until the next deadline.
    calls = s_deadline.call_args_list
    deadlines = s_deadline.spy_return_list
    delays = [c.args[0] for c in m_asyncio.sleep.call_args_list]
    assert len(calls) >= 2
    assert len(delays) >= 2
    assert calls[0].args[0] <= tick_starts[0]
    for idx, (call, deadline, delay) in enumerate(zip(calls, deadlines, delays, strict=False)):
        prev_deadline, now, call_interval = call.args
        assert call_interval == interval
        assert now >= tick_starts[idx] + tick_duration  # After the tick
        assert delay == pytest.approx(deadline - now)
        assert delay < interval
        if idx > 0:
            assert prev_deadline == deadlines[idx - 1]

    # Cancelled if interval <= 0
    s_tick.reset_mock()
    config.broadcast_interval = timedelta()
    async with utils.task_context(bc.repeat()) as task:
        await asyncio.sleep(0.01)
        assert task.done()
    assert s_tick.await_count == 0


async def test_lifespan(s_publish: Mock):
    cmder = command.CV.get()

    async with broadcast.lifespan():
        assert cmder.on_block_change is not None
        await asyncio.sleep(0.05)

    assert cmder.on_block_change is None
    assert published(s_publish, STATE_TOPIC)
    assert published(s_publish, HISTORY_TOPIC)
