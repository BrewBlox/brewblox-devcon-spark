"""
Tests brewblox_devcon_spark.commander_sim
"""

import pytest
from brewblox_service import scheduler

from brewblox_devcon_spark import (commander, commander_sim, commands,
                                   datastore, exceptions, status)
from brewblox_devcon_spark.codec import codec
from brewblox_devcon_spark.commands import (GROUP_LIST_KEY, OBJECT_DATA_KEY,
                                            OBJECT_LIST_KEY, OBJECT_NID_KEY,
                                            OBJECT_TYPE_KEY)


@pytest.fixture
def app(app):
    scheduler.setup(app)
    status.setup(app)
    commander_sim.setup(app)
    datastore.setup(app)
    codec.setup(app)
    return app


@pytest.fixture
def sim(app):
    return commander.get_commander(app)


@pytest.fixture
def object_args():
    return {
        GROUP_LIST_KEY: [0],
        OBJECT_TYPE_KEY: 302,  # TempSensorOneWire
        OBJECT_DATA_KEY: b'\x00'
    }


async def test_create(app, client, object_args, sim):
    cmd = commands.CreateObjectCommand

    created = await sim.execute(cmd.from_args(**object_args))
    assert OBJECT_NID_KEY in created

    # Ok to recreate without ID
    other = await sim.execute(cmd.from_args(**object_args))
    assert other != created

    # Object ID already exists
    with pytest.raises(exceptions.CommandException):
        await sim.execute(cmd.from_args(**created))

    # 100 is reserved for system objects
    with pytest.raises(exceptions.CommandException):
        await sim.execute(cmd.from_args(**object_args, object_nid=100))


async def test_crud(app, client, object_args, sim):
    create_cmd = commands.CreateObjectCommand
    delete_cmd = commands.DeleteObjectCommand
    read_cmd = commands.ReadObjectCommand
    write_cmd = commands.WriteObjectCommand

    created = await sim.execute(create_cmd.from_args(**object_args))

    read_args = {OBJECT_NID_KEY: created[OBJECT_NID_KEY]}
    assert await sim.execute(read_cmd.from_args(**read_args)) == created

    created[GROUP_LIST_KEY] = [0, 1]
    assert await sim.execute(write_cmd.from_args(**created)) == created
    assert await sim.execute(read_cmd.from_args(**read_args)) == created

    with pytest.raises(exceptions.CommandException):
        # Can't assign system group
        await sim.execute(write_cmd.from_args(**{**created, **{GROUP_LIST_KEY: [0, commands.SYSTEM_GROUP]}}))

    await sim.execute(delete_cmd.from_args(object_nid=read_args[OBJECT_NID_KEY]))

    with pytest.raises(exceptions.CommandException):
        # Create object with system-range ID
        await sim.execute(create_cmd.from_args(**{OBJECT_NID_KEY: 50}, **object_args))

    with pytest.raises(exceptions.CommandException):
        await sim.execute(write_cmd.from_args(**created))

    with pytest.raises(exceptions.CommandException):
        await sim.execute(read_cmd.from_args(**read_args))

    with pytest.raises(exceptions.CommandException):
        await sim.execute(create_cmd.from_args(**{**object_args, **{GROUP_LIST_KEY: [commands.SYSTEM_GROUP]}}))


async def test_stored(app, client, object_args, sim):
    create_cmd = commands.CreateObjectCommand
    read_cmd = commands.ReadStoredObjectCommand
    list_cmd = commands.ListStoredObjectsCommand

    created = await sim.execute(create_cmd.from_args(**object_args))
    read_args = {OBJECT_NID_KEY: created[OBJECT_NID_KEY]}
    assert await sim.execute(read_cmd.from_args(**read_args)) == created

    all_stored = await sim.execute(list_cmd.from_args())
    assert created in all_stored[OBJECT_LIST_KEY]

    with pytest.raises(exceptions.CommandException):
        await sim.execute(read_cmd.from_args(**{OBJECT_NID_KEY: 9001}))


async def test_clear(app, client, object_args, sim):
    create_cmd = commands.CreateObjectCommand
    list_cmd = commands.ListObjectsCommand
    clear_cmd = commands.ClearObjectsCommand

    await sim.execute(create_cmd.from_args(**object_args))
    pre = await sim.execute(list_cmd.from_args())
    await sim.execute(clear_cmd.from_args())
    post = await sim.execute(list_cmd.from_args())

    assert len(post[OBJECT_LIST_KEY]) == len(pre[OBJECT_LIST_KEY]) - 1


async def test_noops(app, client, sim):
    for cmd in [
        commands.FactoryResetCommand,
        commands.RebootCommand
    ]:
        assert await sim.execute(cmd.from_args()) == {}
