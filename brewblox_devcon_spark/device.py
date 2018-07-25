"""
Offers a functional interface to the device functionality
"""

import random
import string
from contextlib import suppress
from functools import partialmethod
from typing import Any, Awaitable, Callable, List, Type, Union

from aiohttp import web
from brewblox_service import brewblox_logger, features

from brewblox_codec_spark import codec
from brewblox_devcon_spark import commander, commands, datastore
from brewblox_devcon_spark.commands import (OBJECT_DATA_KEY, OBJECT_ID_KEY,
                                            OBJECT_LIST_KEY, OBJECT_TYPE_KEY,
                                            PROFILE_LIST_KEY, SYSTEM_ID_KEY)

SERVICE_ID_KEY = 'service_id'
CONTROLLER_ID_KEY = 'controller_id'
OBJECT_LINK_POSTFIX = '<>'
ServiceId_ = str
ControllerId_ = int
FindIdFunc_ = Callable[[datastore.DataStore, Any], Awaitable[Any]]

# Keys are imported from commands for use in this module
# but also to allow other modules (eg. API) to import them from here
# "use" them here to avoid lint errors
_FORWARDED = (
    OBJECT_ID_KEY,
    OBJECT_DATA_KEY,
    OBJECT_TYPE_KEY,
    OBJECT_LIST_KEY,
    PROFILE_LIST_KEY,
    SYSTEM_ID_KEY
)

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
        self._commander: commander.SparkCommander = None
        self._object_store: datastore.DataStore = None
        self._system_store: datastore.DataStore = None
        self._codec: codec.Codec = None

    @property
    def name(self):
        return self._name

    async def startup(self, app: web.Application):
        self._commander = commander.get_commander(app)
        self._object_store = datastore.get_object_store(app)
        self._system_store = datastore.get_system_store(app)
        self._codec = codec.get_codec(app)

    async def shutdown(self, *_):
        pass

    def _get_content_objects(self, content: dict) -> List[dict]:
        objects_to_process = [content]
        with suppress(KeyError):
            objects_to_process += content[OBJECT_LIST_KEY]
        return objects_to_process

    async def _process_data(self,
                            processor_func: codec.TranscodeFunc_,
                            content: dict
                            ) -> Awaitable[dict]:
        objects_to_process = self._get_content_objects(content)

        for obj in objects_to_process:
            with suppress(KeyError):
                new_type, new_data = await processor_func(
                    obj[OBJECT_TYPE_KEY],
                    obj[OBJECT_DATA_KEY]
                )
                obj[OBJECT_TYPE_KEY] = new_type
                obj[OBJECT_DATA_KEY] = new_data

        return content

    async def _encode_data(self, content: dict) -> Awaitable[dict]:
        processor_func = self._codec.encode
        return await self._process_data(processor_func, content)

    async def _decode_data(self, content: dict) -> Awaitable[dict]:
        processor_func = self._codec.decode
        return await self._process_data(processor_func, content)

    async def find_controller_id(self,
                                 store: datastore.DataStore,
                                 input_id: Union[ServiceId_, ControllerId_]
                                 ) -> Awaitable[ControllerId_]:
        """
        Finds the controller ID matching service ID input.
        If input is an int, it assumes it already is a controller ID
        """
        if isinstance(input_id, ControllerId_):
            return input_id

        obj = await store.find_unique(SERVICE_ID_KEY, input_id)

        if not obj:
            raise ValueError(f'Service ID [{input_id}] not found in {store}')

        return obj[CONTROLLER_ID_KEY]

    async def find_service_id(self,
                              store: datastore.DataStore,
                              input_id: Union[ServiceId_, ControllerId_]
                              ) -> Awaitable[ServiceId_]:
        """
        Finds the service ID matching controller ID input.
        If input is a string, it assumes it already is a service ID.
        """
        if isinstance(input_id, ServiceId_):
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

    async def _resolve_id(self, finder_func: FindIdFunc_, content: dict) -> Awaitable[dict]:
        objects_to_process = self._get_content_objects(content)

        async def resolve_key(key: str, store: datastore.DataStore):
            for obj in objects_to_process:
                with suppress(KeyError):
                    obj[key] = await finder_func(self, store, obj[key])

        await resolve_key(OBJECT_ID_KEY, self._object_store)
        await resolve_key(SYSTEM_ID_KEY, self._system_store)
        return content

    _resolve_controller_id = partialmethod(_resolve_id, find_controller_id)
    _resolve_service_id = partialmethod(_resolve_id, find_service_id)

    async def _resolve_links(self,
                             finder_func: FindIdFunc_,
                             content: dict
                             ) -> Awaitable[dict]:
        store = self._object_store
        objects_to_process = self._get_content_objects(content)

        async def traverse(data):
            for k, v in data.items():
                if isinstance(v, dict):
                    await traverse(v)
                elif str(k).endswith(OBJECT_LINK_POSTFIX):
                    data[k] = await finder_func(store, v)

        for obj in objects_to_process:
            with suppress(KeyError):
                await traverse(obj[OBJECT_DATA_KEY])

        return content

    _resolve_controller_links = partialmethod(_resolve_links, find_controller_id)
    _resolve_service_links = partialmethod(_resolve_links, find_service_id)

    async def _execute(self,
                       command_type: Type[commands.Command],
                       content_: dict = None,
                       **kwargs
                       ) -> Awaitable[dict]:
        # Allow a combination of a dict containing arguments, and loose kwargs
        content = content_ or dict()
        content.update(kwargs)

        try:

            # pre-processing
            for afunc in [
                self._resolve_controller_id,
                self._resolve_controller_links,
                self._encode_data,
            ]:
                content = await afunc(content)

            # execute
            retval = await self._commander.execute(
                command_type.from_decoded(content)
            )

            # post-processing
            for afunc in [
                self._decode_data,
                self._resolve_service_links,
                self._resolve_service_id,
            ]:
                retval = await afunc(retval)

            return retval

        except Exception as ex:
            LOGGER.debug(f'Failed to execute {command_type}: {type(ex).__name__}({ex})', exc_info=True)
            raise ex

    read_object = partialmethod(_execute, commands.ReadObjectCommand)
    write_object = partialmethod(_execute, commands.WriteObjectCommand)
    create_object = partialmethod(_execute, commands.CreateObjectCommand)
    delete_object = partialmethod(_execute, commands.DeleteObjectCommand)
    read_system_object = partialmethod(_execute, commands.ReadSystemObjectCommand)
    write_system_object = partialmethod(_execute, commands.WriteSystemObjectCommand)
    read_active_profiles = partialmethod(_execute, commands.ReadActiveProfilesCommand)
    write_active_profiles = partialmethod(_execute, commands.WriteActiveProfilesCommand)
    list_active_objects = partialmethod(_execute, commands.ListActiveObjectsCommand)
    list_saved_objects = partialmethod(_execute, commands.ListSavedObjectsCommand)
    list_system_objects = partialmethod(_execute, commands.ListSystemObjectsCommand)
    clear_profile = partialmethod(_execute, commands.ClearProfileCommand)
    factory_reset = partialmethod(_execute, commands.FactoryResetCommand)
    restart = partialmethod(_execute, commands.RestartCommand)
