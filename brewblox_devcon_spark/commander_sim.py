"""
Monkey patches commander.SparkCommander to not require an actual connection.
"""

from contextlib import suppress
from copy import deepcopy
from datetime import datetime
from functools import partial
from itertools import count
from typing import List

from aiohttp import web
from brewblox_service import brewblox_logger, features

from brewblox_devcon_spark import commander, commands, exceptions, status
from brewblox_devcon_spark.codec import codec
from brewblox_devcon_spark.commands import (OBJECT_DATA_KEY, OBJECT_ID_KEY,
                                            OBJECT_LIST_KEY, OBJECT_TYPE_KEY,
                                            PROFILE_LIST_KEY)

OBJECT_ID_START = 100
LOGGER = brewblox_logger(__name__)


def setup(app: web.Application):
    # Register as a SparkCommander, so features.get(app, SparkCommander) still works
    features.add(app, SimulationCommander(app), key=commander.SparkCommander)
    # Before returning, the simulator encodes + decodes values
    # We want to avoid stripping readonly values here
    features.add(app, codec.Codec(app, strip_readonly=False), key='sim_codec')


def modify_ticks(start_time, obj):
    elapsed = datetime.now() - start_time
    obj_data = obj[OBJECT_DATA_KEY]
    obj_data['millisSinceBoot'] = elapsed.total_seconds() * 1000
    obj_data['secondsSinceEpoch'] = start_time.timestamp() + elapsed.total_seconds()


class SimulationResponder():

    async def startup(self, app: web.Application):
        self._app = app
        self._start_time = datetime.now()
        self._id_counter = count(start=OBJECT_ID_START)
        self._codec = features.get(app, key='sim_codec')

        self._command_funcs = {
            commands.ReadObjectCommand: self._read_object,
            commands.WriteObjectCommand: self._write_object,
            commands.CreateObjectCommand: self._create_object,
            commands.DeleteObjectCommand: self._delete_object,
            commands.ListObjectsCommand: self._list_objects,
            commands.ReadStoredObjectCommand: self._read_stored_object,
            commands.ListStoredObjectsCommand: self._list_stored_objects,
            commands.ClearObjectsCommand: self._clear_objects,
            commands.FactoryResetCommand: self._factory_reset,
            commands.RebootCommand: self._reboot,
        }

        self._modifiers = {
            'Ticks': partial(modify_ticks, self._start_time),
        }

        self._objects = {
            1: {
                OBJECT_ID_KEY: 1,
                OBJECT_TYPE_KEY: 'Profiles',
                PROFILE_LIST_KEY: self._all_profiles,
                OBJECT_DATA_KEY: {
                    'active': [0]
                },
            },
            2: {
                OBJECT_ID_KEY: 2,
                OBJECT_TYPE_KEY: 'SysInfo',
                PROFILE_LIST_KEY: self._all_profiles,
                OBJECT_DATA_KEY: {
                    'deviceId': 'c2ltdWxhdG9y'
                },
            },
            3: {
                OBJECT_ID_KEY: 3,
                OBJECT_TYPE_KEY: 'Ticks',
                PROFILE_LIST_KEY: self._all_profiles,
                OBJECT_DATA_KEY: {
                    'millisSinceBoot': 0,
                    'secondsSinceEpoch': 0,
                },
            },
            4: {
                OBJECT_ID_KEY: 4,
                OBJECT_TYPE_KEY: 'OneWireBus',
                PROFILE_LIST_KEY: self._all_profiles,
                OBJECT_DATA_KEY: {},
            },
        }

    @property
    def _all_profiles(self):
        return [i for i in range(8)]

    @property
    def _active_profiles(self):
        return self._objects[1][OBJECT_DATA_KEY]['active']

    @staticmethod
    def _get_content_objects(content: dict) -> List[dict]:
        objects_to_process = [content]
        with suppress(KeyError):
            objects_to_process += content[OBJECT_LIST_KEY]
        return objects_to_process

    async def respond(self, cmd) -> commands.Command:
        # Encode + decode request
        args = cmd.from_encoded(cmd.encoded_request, None).decoded_request

        for obj in self._get_content_objects(args):
            with suppress(KeyError):
                dec_type, dec_data = await self._codec.decode(
                    obj[OBJECT_TYPE_KEY],
                    obj[OBJECT_DATA_KEY]
                )
                obj.update({
                    OBJECT_TYPE_KEY: dec_type,
                    OBJECT_DATA_KEY: dec_data
                })

        func = self._command_funcs[type(cmd)]
        retv = await func(args)
        retv = deepcopy(retv) if retv else dict()

        for obj in self._get_content_objects(retv):
            with suppress(KeyError):
                enc_type, enc_data = await self._codec.encode(
                    obj[OBJECT_TYPE_KEY],
                    obj[OBJECT_DATA_KEY]
                )
                obj.update({
                    OBJECT_TYPE_KEY: enc_type,
                    OBJECT_DATA_KEY: enc_data
                })

        # Encode response, force decoding by creating new command
        encoding_cmd = cmd.from_decoded(cmd.decoded_request, retv)
        return cmd.from_encoded(encoding_cmd.encoded_request, encoding_cmd.encoded_response)

    def _get_obj(self, id):
        obj = self._objects[id]
        mod = self._modifiers.get(obj[OBJECT_TYPE_KEY], lambda o: o)
        mod(obj)

        if id < OBJECT_ID_START:
            return obj  # system object

        if set(obj[PROFILE_LIST_KEY]) & set(self._active_profiles):
            return obj
        else:
            return {
                OBJECT_ID_KEY: obj[OBJECT_ID_KEY],
                OBJECT_TYPE_KEY: 'InactiveObject',
                PROFILE_LIST_KEY: obj[PROFILE_LIST_KEY],
                OBJECT_DATA_KEY: {'actualType': obj[OBJECT_TYPE_KEY]},
            }

    async def _read_object(self, request):
        try:
            return self._get_obj(request[OBJECT_ID_KEY])
        except KeyError:
            raise exceptions.CommandException(f'{request} not found')

    async def _write_object(self, request):
        key = request[OBJECT_ID_KEY]
        if key not in self._objects:
            raise exceptions.CommandException(f'{key} not found')

        self._objects[key] = request
        return self._get_obj(key)

    async def _create_object(self, request):
        key = request.get(OBJECT_ID_KEY)
        obj = request

        if not key:
            key = next(self._id_counter)
            obj[OBJECT_ID_KEY] = key
        elif key < OBJECT_ID_START:
            raise exceptions.CommandException(f'Id {key} is reserved for system objects')
        elif key in self._objects:
            raise exceptions.CommandException(f'Object {key} already exists')

        self._objects[key] = obj
        return obj

    async def _delete_object(self, request):
        key = request[OBJECT_ID_KEY]
        del self._objects[key]

    async def _list_objects(self, request):
        return {
            OBJECT_LIST_KEY: [self._get_obj(id) for id in self._objects.keys()]
        }

    async def _read_stored_object(self, request):
        try:
            return self._objects[request[OBJECT_ID_KEY]]
        except KeyError:
            raise exceptions.CommandException(f'{request} not found')

    async def _list_stored_objects(self, request):
        return {
            OBJECT_LIST_KEY: [obj for obj in self._objects.values()]
        }

    async def _clear_objects(self, request):
        self._objects = {k: v for k, v in self._objects.items() if k < OBJECT_ID_START}

    async def _factory_reset(self, request):
        await self.startup(self._app)

    async def _reboot(self, request):
        self._start_time = datetime.now()


class SimulationCommander(commander.SparkCommander):

    def __init__(self, app: web.Application):
        super().__init__(app)
        self._responder = SimulationResponder()

    async def startup(self, app: web.Application):
        await self._responder.startup(app)
        status.get_status(app).connected.set()

    async def shutdown(self, _):
        pass

    async def execute(self, command: commands.Command) -> dict:
        return (await self._responder.respond(command)).decoded_response
