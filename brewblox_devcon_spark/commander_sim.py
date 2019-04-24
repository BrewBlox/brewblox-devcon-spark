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
from brewblox_devcon_spark.commands import (GROUP_LIST_KEY, OBJECT_DATA_KEY,
                                            OBJECT_ID_LIST_KEY,
                                            OBJECT_INTERFACE_KEY,
                                            OBJECT_LIST_KEY, OBJECT_NID_KEY,
                                            OBJECT_TYPE_KEY, SYSTEM_GROUP)
from brewblox_devcon_spark.datastore import (DISPLAY_SETTINGS_NID,
                                             GROUPS_NID,
                                             OBJECT_NID_START,
                                             ONEWIREBUS_NID,
                                             SYSINFO_NID,
                                             SYSTIME_NID,
                                             TOUCH_SETTINGS_NID,
                                             WIFI_SETTINGS_NID)

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
        self._id_counter = count(start=OBJECT_NID_START)
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
            commands.ListCompatibleObjectsCommand: self._list_compatible_objects,
            commands.DiscoverObjectsCommand: self._discover_objects,
        }

        self._modifiers = {
            'Ticks': partial(modify_ticks, self._start_time),
        }

        self._objects = {
            GROUPS_NID: {
                OBJECT_NID_KEY: GROUPS_NID,
                OBJECT_TYPE_KEY: 'Groups',
                GROUP_LIST_KEY: [SYSTEM_GROUP],
                OBJECT_DATA_KEY: {
                    'active': [0, SYSTEM_GROUP]
                },
            },
            SYSINFO_NID: {
                OBJECT_NID_KEY: SYSINFO_NID,
                OBJECT_TYPE_KEY: 'SysInfo',
                GROUP_LIST_KEY: [SYSTEM_GROUP],
                OBJECT_DATA_KEY: {
                    'deviceId': 'FACADE'
                },
            },
            SYSTIME_NID: {
                OBJECT_NID_KEY: SYSTIME_NID,
                OBJECT_TYPE_KEY: 'Ticks',
                GROUP_LIST_KEY: [SYSTEM_GROUP],
                OBJECT_DATA_KEY: {
                    'millisSinceBoot': 0,
                    'secondsSinceEpoch': 0,
                },
            },
            ONEWIREBUS_NID: {
                OBJECT_NID_KEY: ONEWIREBUS_NID,
                OBJECT_TYPE_KEY: 'OneWireBus',
                GROUP_LIST_KEY: [SYSTEM_GROUP],
                OBJECT_DATA_KEY: {},
            },
            WIFI_SETTINGS_NID: {
                OBJECT_NID_KEY: WIFI_SETTINGS_NID,
                OBJECT_TYPE_KEY: 'WiFiSettings',
                GROUP_LIST_KEY: [SYSTEM_GROUP],
                OBJECT_DATA_KEY: {},
            },
            TOUCH_SETTINGS_NID: {
                OBJECT_NID_KEY: TOUCH_SETTINGS_NID,
                OBJECT_TYPE_KEY: 'TouchSettings',
                GROUP_LIST_KEY: [SYSTEM_GROUP],
                OBJECT_DATA_KEY: {},
            },
            DISPLAY_SETTINGS_NID: {
                OBJECT_NID_KEY: DISPLAY_SETTINGS_NID,
                OBJECT_TYPE_KEY: 'DisplaySettings',
                GROUP_LIST_KEY: [SYSTEM_GROUP],
                OBJECT_DATA_KEY: {},
            },
        }

    @property
    def _active_groups(self):
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
            with suppress(KeyError):
                dec_type = await self._codec.decode(obj[OBJECT_INTERFACE_KEY])
                obj[OBJECT_INTERFACE_KEY] = dec_type

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
            with suppress(KeyError):
                enc_type = await self._codec.encode(obj[OBJECT_INTERFACE_KEY])
                obj[OBJECT_INTERFACE_KEY] = enc_type

        # Encode response, force decoding by creating new command
        encoding_cmd = cmd.from_decoded(cmd.decoded_request, retv)
        return cmd.from_encoded(encoding_cmd.encoded_request, encoding_cmd.encoded_response)

    def _get_obj(self, id):
        obj = self._objects[id]
        mod = self._modifiers.get(obj[OBJECT_TYPE_KEY], lambda o: o)
        mod(obj)

        if id < OBJECT_NID_START:
            return obj  # system object

        if set(obj[GROUP_LIST_KEY]) & set(self._active_groups):
            return obj
        else:
            return {
                OBJECT_NID_KEY: obj[OBJECT_NID_KEY],
                OBJECT_TYPE_KEY: 'InactiveObject',
                GROUP_LIST_KEY: obj[GROUP_LIST_KEY],
                OBJECT_DATA_KEY: {'actualType': obj[OBJECT_TYPE_KEY]},
            }

    async def _read_object(self, request):
        try:
            return self._get_obj(request[OBJECT_NID_KEY])
        except KeyError:
            raise exceptions.CommandException(f'{request} not found')

    async def _write_object(self, request):
        key = request[OBJECT_NID_KEY]
        if key not in self._objects:
            raise exceptions.CommandException(f'{key} not found')
        elif SYSTEM_GROUP in request[GROUP_LIST_KEY] and key >= OBJECT_NID_START:
            raise exceptions.CommandException(f'Group {SYSTEM_GROUP} is reserved for system objects')

        self._objects[key] = request
        return self._get_obj(key)

    async def _create_object(self, request):
        key = request.get(OBJECT_NID_KEY)
        obj = request

        if not key:
            key = next(self._id_counter)
            obj[OBJECT_NID_KEY] = key
        elif key < OBJECT_NID_START:
            raise exceptions.CommandException(f'Id {key} is reserved for system objects')
        elif key in self._objects:
            raise exceptions.CommandException(f'Object {key} already exists')

        if SYSTEM_GROUP in obj[GROUP_LIST_KEY]:
            raise exceptions.CommandException(f'Group {SYSTEM_GROUP} is reserved for system objects')

        self._objects[key] = obj
        return obj

    async def _delete_object(self, request):
        key = request[OBJECT_NID_KEY]
        del self._objects[key]

    async def _list_objects(self, request):
        return {
            OBJECT_LIST_KEY: [self._get_obj(id) for id in self._objects.keys()]
        }

    async def _read_stored_object(self, request):
        try:
            return self._objects[request[OBJECT_NID_KEY]]
        except KeyError:
            raise exceptions.CommandException(f'{request} not found')

    async def _list_stored_objects(self, request):
        return {
            OBJECT_LIST_KEY: list(self._objects.values())
        }

    async def _list_compatible_objects(self, request):
        return {
            OBJECT_ID_LIST_KEY: [{OBJECT_NID_KEY: k} for k in self._objects.keys()]
        }

    async def _discover_objects(self, request):
        return {
            OBJECT_LIST_KEY: [{
                OBJECT_NID_KEY: DISPLAY_SETTINGS_NID,
                OBJECT_INTERFACE_KEY: 'DisplaySettings',
            }]
        }

    async def _clear_objects(self, request):
        self._objects = {k: v for k, v in self._objects.items() if k < OBJECT_NID_START}

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
