"""
Tests brewblox_devcon_spark.commander_sim
"""

import pytest
from brewblox_service import scheduler

from brewblox_devcon_spark import (codec, commander, commander_sim, commands,
                                   const, datastore, exceptions,
                                   service_status)


@pytest.fixture
def app(app):
    scheduler.setup(app)
    service_status.setup(app)
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
        'groups': [0],
        'type': 302,  # TempSensorOneWire
        'data': b'\x00'
    }


async def test_create(app, client, object_args, sim):
    cmd = commands.CreateObjectCommand

    created = await sim.execute(cmd.from_args(**object_args))
    assert 'nid' in created

    # Ok to recreate without ID
    other = await sim.execute(cmd.from_args(**object_args))
    assert other != created

    # Object ID already exists
    with pytest.raises(exceptions.CommandException):
        await sim.execute(cmd.from_args(**created))

    # 100 is reserved for system objects
    with pytest.raises(exceptions.CommandException):
        await sim.execute(cmd.from_args(**object_args, nid=100))


async def test_crud(app, client, object_args, sim):
    create_cmd = commands.CreateObjectCommand
    delete_cmd = commands.DeleteObjectCommand
    read_cmd = commands.ReadObjectCommand
    write_cmd = commands.WriteObjectCommand

    created = await sim.execute(create_cmd.from_args(**object_args))

    read_args = {'nid': created['nid']}
    assert await sim.execute(read_cmd.from_args(**read_args)) == created

    created['groups'] = [0, 1]
    assert await sim.execute(write_cmd.from_args(**created)) == created
    assert await sim.execute(read_cmd.from_args(**read_args)) == created

    with pytest.raises(exceptions.CommandException):
        # Can't assign system group
        await sim.execute(write_cmd.from_args(**{**created, 'groups': [0, const.SYSTEM_GROUP]}))

    await sim.execute(delete_cmd.from_args(nid=read_args['nid']))

    with pytest.raises(exceptions.CommandException):
        # Create object with system-range ID
        await sim.execute(create_cmd.from_args(**{'nid': 50}, **object_args))

    with pytest.raises(exceptions.CommandException):
        await sim.execute(write_cmd.from_args(**created))

    with pytest.raises(exceptions.CommandException):
        await sim.execute(read_cmd.from_args(**read_args))

    with pytest.raises(exceptions.CommandException):
        await sim.execute(create_cmd.from_args(**{**object_args, 'groups': [const.SYSTEM_GROUP]}))


async def test_stored(app, client, object_args, sim):
    create_cmd = commands.CreateObjectCommand
    read_cmd = commands.ReadStoredObjectCommand
    list_cmd = commands.ListStoredObjectsCommand

    created = await sim.execute(create_cmd.from_args(**object_args))
    read_args = {'nid': created['nid']}
    assert await sim.execute(read_cmd.from_args(**read_args)) == created

    all_stored = await sim.execute(list_cmd.from_args())
    assert created in all_stored['objects']

    with pytest.raises(exceptions.CommandException):
        await sim.execute(read_cmd.from_args(nid=9001))


async def test_clear(app, client, object_args, sim):
    create_cmd = commands.CreateObjectCommand
    list_cmd = commands.ListObjectsCommand
    clear_cmd = commands.ClearObjectsCommand

    await sim.execute(create_cmd.from_args(**object_args))
    pre = await sim.execute(list_cmd.from_args())
    await sim.execute(clear_cmd.from_args())
    post = await sim.execute(list_cmd.from_args())

    assert len(post['objects']) == len(pre['objects']) - 1


async def test_non_responsive(app, client, sim):
    for cmd in [
        commands.FactoryResetCommand,
        commands.RebootCommand
    ]:
        with pytest.raises(exceptions.CommandTimeout):
            await sim.execute(cmd.from_args())


async def test_updating(app, client, sim):
    await sim.start_update(0)
    with pytest.raises(exceptions.UpdateInProgress):
        await sim.execute(commands.ListObjectsCommand.from_args())


async def test_inactive(app, client, object_args, sim):
    cdc = codec.get_codec(app)
    create_cmd = commands.CreateObjectCommand
    read_cmd = commands.ReadObjectCommand
    write_cmd = commands.WriteObjectCommand

    object_args['groups'] = []
    created = await sim.execute(create_cmd.from_args(**object_args))
    obj = await sim.execute(read_cmd.from_args(nid=created['nid']))
    assert await cdc.decode(obj['type']) == 'InactiveObject'
    assert obj['nid'] == created['nid']

    await sim.execute(write_cmd.from_args(**obj))
