"""
Offers a functional interface to the device functionality
"""

import random
import string
from functools import partialmethod
from typing import Awaitable, Callable, List, Type, Union

import dpath
from aiohttp import web
from brewblox_service import brewblox_logger, features

from brewblox_codec_spark import codec
from brewblox_devcon_spark import commander, commands, datastore
from brewblox_devcon_spark.commands import (FLAGS_KEY, OBJECT_DATA_KEY,  # noqa
                                            OBJECT_ID_KEY, OBJECT_LIST_KEY,
                                            OBJECT_TYPE_KEY, PROFILE_ID_KEY,
                                            PROFILE_LIST_KEY, SYSTEM_ID_KEY)

SERVICE_ID_KEY = 'service_id'
CONTROLLER_ID_KEY = 'controller_id'

LOGGER = brewblox_logger(__name__)


def get_controller(app: web.Application) -> 'SparkController':
    return features.get(app, SparkController)


def setup(app: web.Application):
    features.add(app, SparkController(name=app['config']['name'], app=app))


class ControllerException(Exception):
    pass


def random_string():
    return 'generated|' + ''.join([
        random.choice(string.ascii_letters + string.digits)
        for n in range(32)
    ])


class SparkController(features.ServiceFeature):

    def __init__(self, name: str, app: web.Application):
        super().__init__(app)

        self._name = name
        self._active_profile = 0

        self._commander: commander.SparkCommander = None
        self._object_store: datastore.DataStore = None
        self._system_store: datastore.DataStore = None
        self._codec: codec.Codec = None

    @property
    def name(self):
        return self._name

    @property
    def active_profile(self) -> int:
        return self._active_profile

    @active_profile.setter
    def active_profile(self, profile_id: int):
        self._active_profile = profile_id

    async def startup(self, app: web.Application):
        self._commander = commander.get_commander(app)
        self._object_store = datastore.get_object_store(app)
        self._system_store = datastore.get_system_store(app)
        self._codec = codec.get_codec(app)

    async def shutdown(self, *_):
        pass

    async def _process_data(self,
                            processor_func: codec.TranscodeFunc_,
                            content: dict
                            ) -> Awaitable[dict]:
        # Looks for codec data, and converts it
        # A type ID is always present in the same dict as the data
        for path in [p for (p, _) in dpath.util.search(content, f'**/{OBJECT_DATA_KEY}', yielded=True)]:

            # find path to dict containing both type and data
            parent_key = '/'.join(path.split('/')[:-1])
            parent = content if not parent_key else dpath.util.get(content, parent_key)

            new_type, new_data = await processor_func(
                parent[OBJECT_TYPE_KEY],
                parent[OBJECT_DATA_KEY]
            )

            parent[OBJECT_TYPE_KEY] = new_type
            parent[OBJECT_DATA_KEY] = new_data

        return content

    async def _encode_data(self, content: dict) -> Awaitable[dict]:
        processor_func = self._codec.encode
        return await self._process_data(processor_func, content)

    async def _decode_data(self, content: dict) -> Awaitable[dict]:
        processor_func = self._codec.decode
        return await self._process_data(processor_func, content)

    async def find_controller_id(self,
                                 store: datastore.DataStore,
                                 input_id: Union[str, List[int]]
                                 ) -> Awaitable[List[int]]:
        """
        Finds the controller ID matching service ID input.
        If input is a list of ints, it assumes it already is a controller ID
        """
        if isinstance(input_id, list) and all([isinstance(i, int) for i in input_id]):
            return input_id

        obj = await store.find_unique(SERVICE_ID_KEY, input_id)

        if not obj:
            raise ValueError(f'Service ID [{input_id}] not found in {store}')

        return obj[CONTROLLER_ID_KEY]

    async def find_service_id(self,
                              store: datastore.DataStore,
                              input_id: Union[str, List[int]]
                              ) -> Awaitable[str]:
        """
        Finds the service ID matching controller ID input.
        If input is a string, it assumes it already is a service ID.
        """
        if isinstance(input_id, str):
            return input_id

        service_id = None

        try:
            # Get first item from data store with correct controller ID,
            # and that has a service ID defined
            objects = await store.find(CONTROLLER_ID_KEY, input_id)
            service_id = next(o.get(SERVICE_ID_KEY) for o in objects)
        except StopIteration:
            # If service ID not found, randomly generate one
            service_id = random_string()
            await store.insert_unique(
                SERVICE_ID_KEY,
                {
                    SERVICE_ID_KEY: service_id,
                    CONTROLLER_ID_KEY: input_id
                }
            )

        return service_id

    async def _resolve_id(self, resolver: Callable, content: dict) -> Awaitable[dict]:
        async def resolve_key(key: str, store: datastore.DataStore):
            for path, id in dpath.util.search(content, f'**/{key}', yielded=True):
                dpath.util.set(content, path, await resolver(self, store, id))

        await resolve_key(OBJECT_ID_KEY, self._object_store)
        await resolve_key(SYSTEM_ID_KEY, self._system_store)

        return content

    _resolve_controller_id = partialmethod(_resolve_id, find_controller_id)
    _resolve_service_id = partialmethod(_resolve_id, find_service_id)

    async def _execute(self,
                       command_type: Type[commands.Command],
                       content_: dict=None,
                       **kwargs
                       ) -> Awaitable[dict]:
        # Allow a combination of a dict containing arguments, and loose kwargs
        content = content_ or dict()
        content.update(kwargs)

        try:

            # pre-processing
            for afunc in [
                self._resolve_controller_id,
                self._encode_data,
            ]:
                content = await afunc(content)

            # execute
            retval = await self._commander.execute(
                command_type().from_decoded(content)
            )

            # post-processing
            for afunc in [
                self._resolve_service_id,
                self._decode_data,
            ]:
                retval = await afunc(retval)

            return retval

        except Exception as ex:
            LOGGER.debug(f'Failed to execute {command_type()}: {type(ex).__name__}({ex})', exc_info=True)
            raise ex

    read_value = partialmethod(_execute, commands.ReadValueCommand)
    write_value = partialmethod(_execute, commands.WriteValueCommand)
    create_object = partialmethod(_execute, commands.CreateObjectCommand)
    delete_object = partialmethod(_execute, commands.DeleteObjectCommand)
    list_objects = partialmethod(_execute, commands.ListObjectsCommand)
    free_slot = partialmethod(_execute, commands.FreeSlotCommand)
    create_profile = partialmethod(_execute, commands.CreateProfileCommand)
    delete_profile = partialmethod(_execute, commands.DeleteProfileCommand)
    activate_profile = partialmethod(_execute, commands.ActivateProfileCommand)
    log_values = partialmethod(_execute, commands.LogValuesCommand)
    reset = partialmethod(_execute, commands.ResetCommand)
    free_slot_root = partialmethod(_execute, commands.FreeSlotRootCommand)
    list_profiles = partialmethod(_execute, commands.ListProfilesCommand)
    read_system_value = partialmethod(_execute, commands.ReadSystemValueCommand)
    write_system_value = partialmethod(_execute, commands.WriteSystemValueCommand)
