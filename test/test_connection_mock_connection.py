"""
Tests for the in-process firmware mock:
writes by presence, and CHANGED read-alls.
"""

import asyncio
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI

from brewblox_devcon_spark import codec, command, const, state_machine
from brewblox_devcon_spark.codec.pb2 import ActuatorPwm_pb2, Balancer_pb2, SetpointProfile_pb2
from brewblox_devcon_spark.connection import connection_handler, mock_connection
from brewblox_devcon_spark.connection.mock_connection import merge_present
from brewblox_devcon_spark.models import FirmwareBlock, FirmwareBlockIdentity, ReadMode

TESTED = mock_connection.__name__


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with connection_handler.lifespan():
        yield


@pytest.fixture(autouse=True)
def app() -> FastAPI:
    state_machine.setup()
    codec.setup()
    connection_handler.setup()
    command.setup()
    return FastAPI(lifespan=lifespan)


def test_merge_scalars():
    dest = ActuatorPwm_pb2.Block(enabled=True, period=4000, storedSetting=50 * 4096)

    # Present fields are written, also if zero or false
    merge_present(dest, ActuatorPwm_pb2.Block(enabled=False, storedSetting=0))
    assert dest.HasField('enabled')
    assert not dest.enabled
    assert dest.HasField('storedSetting')
    assert dest.storedSetting == 0

    # Absent fields are kept
    assert dest.period == 4000


def test_merge_messages():
    dest = ActuatorPwm_pb2.Block()
    dest.constraints.min.enabled = True
    dest.constraints.min.value = 10

    src = ActuatorPwm_pb2.Block()
    src.constraints.max.value = 90
    merge_present(dest, src)
    assert dest.constraints.min.enabled
    assert dest.constraints.min.value == 10
    assert dest.constraints.max.value == 90

    # A present, empty message is set present
    src = ActuatorPwm_pb2.Block()
    src.constraints.balanced.SetInParent()
    merge_present(dest, src)
    assert dest.constraints.HasField('balanced')
    assert dest.constraints.min.value == 10


def test_merge_lists():
    dest = SetpointProfile_pb2.Block()
    dest.points.items.add(time=1)
    dest.points.items.add(time=2)

    # List wrappers are replaced whole
    src = SetpointProfile_pb2.Block()
    src.points.items.add(time=3)
    merge_present(dest, src)
    assert [v.time for v in dest.points.items] == [3]

    # An absent wrapper keeps the list
    merge_present(dest, SetpointProfile_pb2.Block(enabled=True))
    assert [v.time for v in dest.points.items] == [3]

    # A present, empty wrapper clears it
    src = SetpointProfile_pb2.Block()
    src.points.SetInParent()
    merge_present(dest, src)
    assert dest.HasField('points')
    assert list(dest.points.items) == []

    # Repeated fields are replaced whole
    dest = Balancer_pb2.Block()
    dest.clients.add(id=1)
    dest.clients.add(id=2)
    src = Balancer_pb2.Block()
    src.clients.add(id=3)
    merge_present(dest, src)
    assert [v.id for v in dest.clients] == [3]


async def test_changed_read(manager):
    state = state_machine.CV.get()
    state.set_enabled(True)
    await asyncio.wait_for(state.wait_connected(), timeout=5)
    cmdr = command.CV.get()

    async def read_changed() -> list[int]:
        # Uptime changes with time: SysInfo may or may not have changed
        blocks = await cmdr.read_all_blocks(ReadMode.CHANGED)
        return [v.nid for v in blocks if v.nid != const.SYS_BLOCK_IDS['SysInfo']]

    # The first CHANGED read of a connection has every block, without names
    blocks = await cmdr.read_all_blocks()
    changed = await cmdr.read_all_blocks(ReadMode.CHANGED)
    assert [v.nid for v in changed] == [v.nid for v in blocks]
    assert all(not v.id for v in changed)

    # Then only the blocks that changed
    assert await read_changed() == []

    created = await cmdr.create_block(FirmwareBlock(id='sensor', nid=0, type='TempSensorMock', data={'setting': 20}))
    assert await read_changed() == [created.nid]

    # Writes by presence
    written = await cmdr.write_block(FirmwareBlock(nid=created.nid, type='TempSensorMock', data={'connected': True}))
    assert written.data['connected'] is True
    assert written.data['setting']['value'] == 20
    assert await read_changed() == [created.nid]

    # A block created again with the same nid and content is changed
    await cmdr.delete_block(FirmwareBlockIdentity(nid=created.nid))
    await cmdr.create_block(
        FirmwareBlock(id='sensor', nid=created.nid, type='TempSensorMock', data={'setting': 20, 'connected': True})
    )
    assert await read_changed() == [created.nid]

    # After clearing blocks, all blocks are changed
    await cmdr.clear_blocks()
    changed = await cmdr.read_all_blocks(ReadMode.CHANGED)
    assert [v.nid for v in changed] == [v.nid for v in blocks]
    await cmdr.factory_reset()
    assert await read_changed() == [v.nid for v in blocks if v.nid != const.SYS_BLOCK_IDS['SysInfo']]
