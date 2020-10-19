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

from brewblox_devcon_spark import (codec, commander, commands, const,
                                   exceptions, service_status)

LOGGER = brewblox_logger(__name__)


def make_device(app: web.Application):
    config = app['config']
    ini = app['ini']

    return service_status.DeviceInfo(
        firmware_version=ini['firmware_version'],
        proto_version=ini['proto_version'],
        firmware_date=ini['firmware_date'],
        proto_date=ini['proto_date'],
        device_id=config['device_id'],
        system_version='sys_version',
        platform='Simulator',
        reset_reason='Simulator reset',
    )


def modify_ticks(start_time, obj):
    elapsed = datetime.now() - start_time
    obj_data = obj['data']
    obj_data['millisSinceBoot'] = elapsed.total_seconds() * 1000
    obj_data['secondsSinceEpoch'] = start_time.timestamp() + elapsed.total_seconds()


class SimulationResponder():

    async def startup(self, app: web.Application):
        self.app = app
        self._start_time = datetime.now()
        self._id_counter = count(start=const.USER_NID_START)
        self._codec = features.get(app, key='sim_codec')

        self._command_funcs = {
            commands.NoopCommand: self._noop_command,
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
            commands.FirmwareUpdateCommand: self._firmware_update,
        }

        self._modifiers = {
            'Ticks': partial(modify_ticks, self._start_time),
        }

        self._objects = {
            const.GROUPS_NID: {
                'nid': const.GROUPS_NID,
                'type': 'Groups',
                'groups': [const.SYSTEM_GROUP],
                'data': {
                    'active': [0, const.SYSTEM_GROUP]
                },
            },
            const.SYSINFO_NID: {
                'nid': const.SYSINFO_NID,
                'type': 'SysInfo',
                'groups': [const.SYSTEM_GROUP],
                'data': {
                    'deviceId': 'FACADE'
                },
            },
            const.SYSTIME_NID: {
                'nid': const.SYSTIME_NID,
                'type': 'Ticks',
                'groups': [const.SYSTEM_GROUP],
                'data': {
                    'millisSinceBoot': 0,
                    'secondsSinceEpoch': 0,
                },
            },
            const.ONEWIREBUS_NID: {
                'nid': const.ONEWIREBUS_NID,
                'type': 'OneWireBus',
                'groups': [const.SYSTEM_GROUP],
                'data': {},
            },
            const.WIFI_SETTINGS_NID: {
                'nid': const.WIFI_SETTINGS_NID,
                'type': 'WiFiSettings',
                'groups': [const.SYSTEM_GROUP],
                'data': {},
            },
            const.TOUCH_SETTINGS_NID: {
                'nid': const.TOUCH_SETTINGS_NID,
                'type': 'TouchSettings',
                'groups': [const.SYSTEM_GROUP],
                'data': {},
            },
            const.DISPLAY_SETTINGS_NID: {
                'nid': const.DISPLAY_SETTINGS_NID,
                'type': 'DisplaySettings',
                'groups': [const.SYSTEM_GROUP],
                'data': {},
            },
            const.SPARK_PINS_NID: {
                'nid': const.SPARK_PINS_NID,
                'type': 'Spark3Pins',
                'groups': [const.SYSTEM_GROUP],
                'data': {
                    'pins': [
                        {'top1': {}},
                        {'top2': {}},
                        {'top3': {}},
                        {'bottom1': {}},
                        {'bottom2': {}},
                    ]
                },
            }

        }

    @property
    def _active_groups(self):
        return self._objects[1]['data']['active']

    @staticmethod
    def _get_content_objects(content: dict) -> List[dict]:
        objects_to_process = [content]
        with suppress(KeyError):
            objects_to_process += content['objects']
        return objects_to_process

    async def respond(self, cmd) -> commands.Command:
        # Encode + decode request
        args = cmd.from_encoded(cmd.encoded_request, None).decoded_request

        for obj in self._get_content_objects(args):
            with suppress(KeyError):
                dec_type, dec_data = await self._codec.decode(
                    obj['type'],
                    obj['data']
                )
                obj.update({
                    'type': dec_type,
                    'data': dec_data
                })
            with suppress(KeyError):
                dec_type = await self._codec.decode(obj['interface'])
                obj['interface'] = dec_type

        func = self._command_funcs[type(cmd)]
        retv = await func(args)
        retv = deepcopy(retv) if retv else dict()

        for obj in self._get_content_objects(retv):
            with suppress(KeyError):
                enc_type, enc_data = await self._codec.encode(
                    obj['type'],
                    obj['data']
                )
                obj.update({
                    'type': enc_type,
                    'data': enc_data
                })
            with suppress(KeyError):
                enc_type = await self._codec.encode(obj['interface'])
                obj['interface'] = enc_type

        # Encode response, force decoding by creating new command
        encoding_cmd = cmd.from_decoded(cmd.decoded_request, retv)
        return cmd.from_encoded(encoding_cmd.encoded_request, encoding_cmd.encoded_response)

    def _get_obj(self, id):
        obj = self._objects[id]
        mod = self._modifiers.get(obj['type'], lambda o: o)
        mod(obj)

        if id < const.USER_NID_START:
            return obj  # system object

        if set(obj['groups']) & set(self._active_groups):
            return obj
        else:
            return {
                'nid': obj['nid'],
                'type': 'InactiveObject',
                'groups': obj['groups'],
                'data': {'actualType': obj['type']},
            }

    async def _noop_command(self, request):
        # Shortcut for actual behavior
        # Noop triggers a welcome message
        # Welcome message is checked, and triggers set_acknowledged()
        service_status.set_acknowledged(self.app, make_device(self.app))

    async def _read_object(self, request):
        try:
            return self._get_obj(request['nid'])
        except KeyError:
            raise exceptions.CommandException(f'{request} not found')

    async def _write_object(self, request):
        key = request['nid']
        if key not in self._objects:
            raise exceptions.CommandException(f'{key} not found')
        elif const.SYSTEM_GROUP in request['groups'] and key >= const.USER_NID_START:
            raise exceptions.CommandException(f'Group {const.SYSTEM_GROUP} is reserved for system objects')

        self._objects[key] = request
        return self._get_obj(key)

    async def _create_object(self, request):
        key = request.get('nid')
        obj = request

        if not key:
            key = next(self._id_counter)
            obj['nid'] = key
        elif key < const.USER_NID_START:
            raise exceptions.CommandException(f'Id {key} is reserved for system objects')
        elif key in self._objects:
            raise exceptions.CommandException(f'Object {key} already exists')

        if const.SYSTEM_GROUP in obj['groups']:
            raise exceptions.CommandException(f'Group {const.SYSTEM_GROUP} is reserved for system objects')

        self._objects[key] = obj
        return obj

    async def _delete_object(self, request):
        key = request['nid']
        del self._objects[key]

    async def _list_objects(self, request):
        return {
            'objects': [self._get_obj(id) for id in self._objects.keys()]
        }

    async def _read_stored_object(self, request):
        try:
            return self._objects[request['nid']]
        except KeyError:
            raise exceptions.CommandException(f'{request} not found')

    async def _list_stored_objects(self, request):
        return {
            'objects': list(self._objects.values())
        }

    async def _list_compatible_objects(self, request):
        return {
            'object_ids': [{'nid': k} for k in self._objects.keys()]
        }

    async def _discover_objects(self, request):
        return {
            'objects': [{
                'nid': const.DISPLAY_SETTINGS_NID,
                'interface': 'DisplaySettings',
            }]
        }

    async def _clear_objects(self, request):
        self._objects = {k: v for k, v in self._objects.items() if k < const.USER_NID_START}

    async def _factory_reset(self, request):
        await self.startup(self.app)
        raise exceptions.CommandTimeout()

    async def _reboot(self, request):
        self._start_time = datetime.now()
        raise exceptions.CommandTimeout()

    async def _firmware_update(self, request):
        pass


class SimulationCommander(commander.SparkCommander):

    def __init__(self, app: web.Application):
        super().__init__(app)
        self._responder = SimulationResponder()

    async def startup(self, app: web.Application):
        await self._responder.startup(app)
        # Normally handled by communication
        service_status.set_connected(app, 'simulation:1234')
        service_status.set_acknowledged(app, make_device(app))

    async def shutdown(self, app: web.Application):
        service_status.set_disconnected(app)

    async def execute(self, command: commands.Command) -> dict:
        return (await self._responder.respond(command)).decoded_response


def setup(app: web.Application):
    # Register as a SparkCommander, so commander.fget(app) still works
    features.add(app, SimulationCommander(app), key=commander.SparkCommander)
    # Before returning, the simulator encodes + decodes values
    # We want to avoid stripping readonly values here
    features.add(app, codec.Codec(app, strip_readonly=False), key='sim_codec')
