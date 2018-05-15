"""
Monkey patches commander.SparkCommander to not require an actual connection.
"""

from brewblox_devcon_spark import commander, commands
from aiohttp import web
from brewblox_service import features
from brewblox_devcon_spark.commands import (OBJECT_DATA_KEY, OBJECT_ID_KEY,
                                            OBJECT_LIST_KEY, OBJECT_TYPE_KEY,
                                            PROFILE_ID_KEY, PROFILE_LIST_KEY,
                                            SYSTEM_ID_KEY)
from functools import partialmethod


def setup(app: web.Application):
    # Register as a SparkCommander, so features.get(app, SparkCommander) still works
    features.add(app, SimulationCommander(app), name=commander.SparkCommander)


class SimulationResponder():

    def __init__(self):
        self._generators = {
            commands.ReadValueCommand: self._read_value,
            commands.WriteValueCommand: self._write_value,
            commands.CreateObjectCommand: self._create_object,
            commands.ListObjectsCommand: self._list_objects,
            commands.CreateProfileCommand: self._create_profile,
            commands.ActivateProfileCommand: self._activate_profile,
            commands.LogValuesCommand: self._log_values,
            commands.ListProfilesCommand: self._list_profiles,
            commands.ReadSystemValueCommand: self._read_system_value,
            commands.WriteSystemValueCommand: self._write_system_value
        }

        self._current_id = [0, 0]
        self._num_profiles = 0
        self._active_profile = 0

        self._system_objects = {
            "2": {
                SYSTEM_ID_KEY: [2],
                OBJECT_TYPE_KEY: 10,
                OBJECT_DATA_KEY: b'\x08\n\x00\x12\x01\xaa\x12\x01\xbb'
            }
        }

        self._objects = {}

    def respond(self, command):
        func = self._generators.get(type(command)) or self._empty_response
        return func(command.decoded_request)

    def _object_id(self, controller_id: list):
        return '~'.join([str(v) for v in controller_id])

    def _next_controller_id(self):
        self._current_id[-1] = (self._current_id[-1] + 1) % 128

        if self._current_id[-1] == 0:
            self._current_id.append(1)

        return self._current_id[:]

    def _empty_response(self, request):
        return dict()

    def _read_value(self, request):
        strkey = self._object_id(request[OBJECT_ID_KEY])
        return self._objects[strkey].copy()

    def _write_value(self, request):
        strkey = self._object_id(request[OBJECT_ID_KEY])
        self._objects[strkey] = request.copy()
        return request.copy()

    def _create_object(self, request):
        id = self._next_controller_id()
        obj = request.copy()
        obj[OBJECT_ID_KEY] = id
        self._objects[self._object_id(id)] = obj
        print(self._objects)
        return {OBJECT_ID_KEY: id[:]}

    def _list_objects(self, request):
        return {OBJECT_LIST_KEY: [o.copy() for o in self._objects.values()]}

    def _create_profile(self, request):
        self._num_profiles += 1
        return {PROFILE_ID_KEY: self._num_profiles}

    def _activate_profile(self, request):
        if request[PROFILE_ID_KEY] > self._num_profiles:
            raise commands.CommandException('Unknown profile ID')

        self._active_profile = request[PROFILE_ID_KEY]
        return dict()

    _log_values = partialmethod(_list_objects)

    def _list_profiles(self, request):
        return {
            PROFILE_ID_KEY: self._active_profile,
            PROFILE_LIST_KEY: [i for i in range(self._num_profiles)]
        }

    def _read_system_value(self, request):
        strkey = self._object_id(request[SYSTEM_ID_KEY])
        return self._system_objects[strkey].copy()

    def _write_system_value(self, request):
        strkey = self._object_id(request[SYSTEM_ID_KEY])
        self._system_objects[strkey] = request.copy()
        return request.copy()


class SimulationCommander(commander.SparkCommander):

    def __init__(self, app: web.Application):
        super().__init__(app)
        self._responder = SimulationResponder()

    async def start(self, *_):
        pass

    async def close(self, *_):
        pass

    async def execute(self, command: commands.Command) -> dict:
        return self._responder.respond(command)
