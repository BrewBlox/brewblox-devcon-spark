"""
Monkey patches commander.SparkCommander to not require an actual connection.
"""

from itertools import count

from brewblox_devcon_spark import commander, commands
from brewblox_devcon_spark.commands import (OBJECT_DATA_KEY, OBJECT_ID_KEY,
                                            OBJECT_LIST_KEY, OBJECT_TYPE_KEY,
                                            PROFILE_ID_KEY, PROFILE_LIST_KEY,
                                            SYSTEM_ID_KEY)


_SIMULATION_OBJECT = {
    OBJECT_ID_KEY: [1, 2, 3],
    OBJECT_TYPE_KEY: 6,
    OBJECT_DATA_KEY: b'\x0f\n\x05\n\x01\xff\x10(\x12\x06\x08\xf2\xc0\x01\x10\x01'
}


_SIMULATION_OBJECT_LIST = {
    OBJECT_LIST_KEY: [_SIMULATION_OBJECT.copy() for i in range(5)]
}


_id_counter = count()


def empty_response(request):
    return dict()


def read_value(request):
    obj = _SIMULATION_OBJECT.copy()
    obj[OBJECT_ID_KEY] = request[OBJECT_ID_KEY]
    return obj


def write_value(request):
    return request


def create_object(request):
    return {OBJECT_ID_KEY: [1, next(_id_counter)]}


def list_objects(request):
    return _SIMULATION_OBJECT_LIST.copy()


def create_profile(request):
    return {PROFILE_ID_KEY: next(_id_counter)}


def log_values(request):
    return _SIMULATION_OBJECT_LIST.copy()


def list_profiles(request):
    return {
        PROFILE_ID_KEY: 6,
        PROFILE_LIST_KEY: [1, 2, 3, 4]
    }


def read_system_value(request):
    obj = _SIMULATION_OBJECT.copy()
    del obj[OBJECT_ID_KEY]
    obj[SYSTEM_ID_KEY] = request[SYSTEM_ID_KEY]
    return obj


def write_system_value(request):
    return request


_SIMULATION_GENERATORS = {
    commands.ReadValueCommand: read_value,
    commands.WriteValueCommand: write_value,
    commands.CreateObjectCommand: create_object,
    commands.ListObjectsCommand: list_objects,
    commands.CreateProfileCommand: create_profile,
    commands.LogValuesCommand: log_values,
    commands.ListProfilesCommand: list_profiles,
    commands.ReadSystemValueCommand: read_system_value,
    commands.WriteSystemValueCommand: write_system_value
}


class SimulationCommander(commander.SparkCommander):

    async def bind(self, *args, **kwargs):
        pass

    async def execute(self, command: commands.Command) -> dict:
        func = _SIMULATION_GENERATORS.get(type(command), empty_response)
        return func(command.decoded_request)
