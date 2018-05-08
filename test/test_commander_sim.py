"""
Tests the simulation commander implementation
"""


import pytest
from brewblox_devcon_spark import commander_sim, commands


@pytest.fixture
async def sim(loop):
    s = commander_sim.SimulationCommander(loop)
    return s


async def test_startup(sim):
    await sim.bind()
    await sim.bind()
    await sim.close()
    await sim.bind()


async def test_read_value(sim):
    cmd = commands.ReadValueCommand().from_args(
        object_id=[8, 4],
        object_type=0
    )

    res = await sim.execute(cmd)
    assert res['object_id'] == [8, 4]


async def test_write_value(sim):
    cmd = commands.WriteValueCommand().from_args(
        object_id=[0, 0],
        object_type=7,
        object_data=b''
    )

    assert await sim.execute(cmd) == cmd.decoded_request


async def test_create_object(sim):
    cmd = commands.CreateObjectCommand().from_args(
        object_type=1,
        object_data=b''
    )

    obj_1 = await sim.execute(cmd)
    assert 'object_id' in obj_1
    assert obj_1 != await sim.execute(cmd)


async def test_delete_object(sim):
    cmd = commands.DeleteObjectCommand().from_args(
        object_id=[1, 2]
    )

    res = await sim.execute(cmd)
    assert not res and res is not None


async def test_list_objects(sim):
    cmd = commands.ListObjectsCommand().from_args(
        profile_id=1
    )

    assert 'objects' in await sim.execute(cmd)


async def test_free_slot(sim):
    cmd = commands.FreeSlotCommand().from_args(
        object_id=[4, 5]
    )

    res = await sim.execute(cmd)
    assert not res and res is not None


async def test_create_profile(sim):
    cmd = commands.CreateProfileCommand().from_args()

    res = await sim.execute(cmd)
    assert 'profile_id' in res
    assert res != await sim.execute(cmd)


async def test_delete_profile(sim):
    cmd = commands.DeleteProfileCommand().from_args(
        profile_id=1
    )

    res = await sim.execute(cmd)
    assert not res and res is not None


async def test_activate_profile(sim):
    cmd = commands.ActivateProfileCommand().from_args(
        profile_id=1
    )

    res = await sim.execute(cmd)
    assert not res and res is not None


async def test_log_values(sim):
    cmd = commands.LogValuesCommand().from_args(
        flags={}
    )

    assert 'objects' in await sim.execute(cmd)


async def test_reset(sim):
    cmd = commands.ResetCommand().from_args(
        flags={}
    )

    res = await sim.execute(cmd)
    assert not res and res is not None


async def test_free_slot_root(sim):
    cmd = commands.FreeSlotRootCommand().from_args(
        system_object_id=[0, 100]
    )

    res = await sim.execute(cmd)
    assert not res and res is not None


async def test_list_profiles(sim):
    cmd = commands.ListProfilesCommand().from_args()

    res = await sim.execute(cmd)
    assert 'profile_id' in res
    assert 'profiles' in res


async def test_read_system_value(sim):
    cmd = commands.ReadSystemValueCommand().from_args(
        system_object_id=[8, 4],
        object_type=0
    )

    res = await sim.execute(cmd)
    assert res['system_object_id'] == [8, 4]


async def test_write_system_value(sim):
    cmd = commands.WriteSystemValueCommand().from_args(
        system_object_id=[0, 0],
        object_type=7,
        object_data=b''
    )

    assert await sim.execute(cmd) == cmd.decoded_request
