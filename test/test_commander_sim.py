"""
Tests brewblox_devcon_spark.commander_sim
"""

from unittest.mock import ANY

import pytest

from brewblox_devcon_spark import (commander, commander_sim, commands,
                                   exceptions)
from brewblox_devcon_spark.commands import (OBJECT_DATA_KEY, OBJECT_ID_KEY,
                                            OBJECT_LIST_KEY, OBJECT_TYPE_KEY,
                                            PROFILE_LIST_KEY)


@pytest.fixture
def app(app):
    commander_sim.setup(app)
    return app


@pytest.fixture
def sim(app):
    return commander.get_commander(app)


@pytest.fixture
def object_args():
    return {
        PROFILE_LIST_KEY: [1, 3, 5],
        OBJECT_TYPE_KEY: 1,
        OBJECT_DATA_KEY: bytes([0x0F]*10)
    }


async def test_create(app, loop, object_args, sim):
    cmd = commands.CreateObjectCommand

    created = await sim.execute(cmd.from_args(**object_args))
    assert 'object_id' in created

    # Ok to recreate without ID
    other = await sim.execute(cmd.from_args(**object_args))
    assert other != created

    # Object ID already exists
    with pytest.raises(exceptions.CommandException):
        await sim.execute(cmd.from_args(**created))


async def test_crud(app, loop, object_args, sim):
    create_cmd = commands.CreateObjectCommand
    delete_cmd = commands.DeleteObjectCommand
    read_cmd = commands.ReadObjectCommand
    write_cmd = commands.WriteObjectCommand

    created = await sim.execute(create_cmd.from_args(**object_args))

    read_args = {
        OBJECT_ID_KEY: created[OBJECT_ID_KEY],
        OBJECT_TYPE_KEY: created[OBJECT_TYPE_KEY]
    }
    assert await sim.execute(read_cmd.from_args(**read_args)) == created

    created[PROFILE_LIST_KEY] = [0, 1, 7]
    assert await sim.execute(write_cmd.from_args(**created)) == created
    assert await sim.execute(read_cmd.from_args(**read_args)) == created

    await sim.execute(delete_cmd.from_args(object_id=read_args[OBJECT_ID_KEY]))

    with pytest.raises(exceptions.CommandException):
        assert await sim.execute(write_cmd.from_args(**created))

    with pytest.raises(exceptions.CommandException):
        assert await sim.execute(read_cmd.from_args(**read_args))


async def test_profiles(app, loop, sim, object_args):
    create_cmd = commands.CreateObjectCommand
    read_cmd = commands.ReadObjectCommand
    set_profile_cmd = commands.WriteActiveProfilesCommand
    get_profile_cmd = commands.ReadActiveProfilesCommand
    active_cmd = commands.ListActiveObjectsCommand
    saved_cmd = commands.ListSavedObjectsCommand
    clear_cmd = commands.ClearProfileCommand

    created = await sim.execute(create_cmd.from_args(**object_args))

    # No profiles active
    assert await sim.execute(get_profile_cmd.from_args()) == {
        PROFILE_LIST_KEY: []
    }
    assert await sim.execute(active_cmd.from_args()) == {
        PROFILE_LIST_KEY: [],
        OBJECT_LIST_KEY: [ANY]
    }
    assert await sim.execute(saved_cmd.from_args()) == {
        PROFILE_LIST_KEY: [],
        OBJECT_LIST_KEY: [ANY, created]
    }

    # Activate profile 1
    active = {PROFILE_LIST_KEY: [1]}
    assert await sim.execute(set_profile_cmd.from_args(**active)) == active
    assert await sim.execute(get_profile_cmd.from_args()) == active
    assert await sim.execute(active_cmd.from_args()) == {
        PROFILE_LIST_KEY: [1],
        OBJECT_LIST_KEY: [ANY, created]
    }
    assert await sim.execute(saved_cmd.from_args()) == {
        PROFILE_LIST_KEY: [1],
        OBJECT_LIST_KEY: [ANY, created]
    }

    # Clear profile 1
    # Profile 1 is still active, but object does not belong to it
    await sim.execute(clear_cmd.from_args(**active))
    assert await sim.execute(get_profile_cmd.from_args()) == active
    assert await sim.execute(active_cmd.from_args()) == {
        PROFILE_LIST_KEY: [1],
        OBJECT_LIST_KEY: [ANY]
    }

    read_args = {
        OBJECT_ID_KEY: created[OBJECT_ID_KEY],
        OBJECT_TYPE_KEY: created[OBJECT_TYPE_KEY]
    }
    updated = await sim.execute(read_cmd.from_args(**read_args))
    assert updated[PROFILE_LIST_KEY] == [3, 5]


async def test_noops(app, loop, sim):
    for cmd in [
        commands.FactoryResetCommand,
        commands.RestartCommand
    ]:
        assert await sim.execute(cmd.from_args()) == {}
