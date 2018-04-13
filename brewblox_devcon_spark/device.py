"""
Offers a functional interface to the device functionality
"""

from functools import partialmethod
from typing import Callable, List, Type, Union

import dpath
from aiohttp import web

from brewblox_codec_spark import codec
from brewblox_devcon_spark import brewblox_logger, commands
from brewblox_devcon_spark.commander import SparkCommander
from brewblox_devcon_spark.datastore import (DataStore, FileDataStore,
                                             MemoryDataStore)

CONTROLLER_KEY = 'controller.spark'
SERVICE_ID_KEY = 'service_id'
CONTROLLER_ID_KEY = 'controller_id'

OBJ_TYPE_TYPE_ = Union[int, str]
OBJ_DATA_TYPE_ = Union[bytes, dict]

LOGGER = LOGGER = brewblox_logger(__name__)


def get_controller(app) -> 'SparkController':
    return app[CONTROLLER_KEY]


def setup(app: Type[web.Application]):
    app[CONTROLLER_KEY] = SparkController(name=app['config']['name'], app=app)


class ControllerException(Exception):
    pass


async def resolve_controller_id(store: DataStore, input_id: str) -> List[int]:
    obj = await store.find_by_id(input_id)
    assert obj, f'Service ID [{input_id}] not found in {store}'
    return obj[CONTROLLER_ID_KEY]


class SparkController():

    def __init__(self, name: str, app=None):
        self._name = name
        self._commander: SparkCommander = None
        self._object_store: FileDataStore = None
        self._system_store: FileDataStore = None
        self._object_cache: MemoryDataStore = None
        self._active_profile = 0

        if app:
            self.setup(app)

    @property
    def name(self):
        return self._name

    def setup(self, app: Type[web.Application]):
        app.on_startup.append(self.start)
        app.on_cleanup.append(self.close)

    async def start(self, app: Type[web.Application]):
        await self.close()

        self._object_cache = MemoryDataStore(
            primary_key=SERVICE_ID_KEY
        )
        await self._object_cache.start(loop=app.loop)

        self._object_store = FileDataStore(
            filename=app['config']['database'],
            read_only=False,
            primary_key=SERVICE_ID_KEY
        )
        await self._object_store.start(loop=app.loop)

        self._system_store = FileDataStore(
            filename=app['config']['system_database'],
            read_only=False,
            primary_key=SERVICE_ID_KEY
        )
        await self._system_store.start(loop=app.loop)

        self._commander = SparkCommander(app.loop)
        await self._commander.bind(loop=app.loop)

    async def close(self, *args, **kwargs):
        [
            await s.close() for s in [
                self._commander,
                self._object_store,
                self._object_cache,
                self._system_store
            ]
            if s is not None
        ]

    def _processed(self, func: Callable, content: dict) -> dict:
        data_key = commands.OBJECT_DATA_KEY
        type_key = commands.OBJECT_TYPE_KEY

        # Looks for codec data, and converts it
        # A type ID is always present in the same dict as the data
        for path, data in dpath.util.search(content, f'**/{data_key}', yielded=True):

            # find path to dict containing both type and data
            parent = '/'.join(path.split('/')[:-1])

            # get the type from the dict that contained data
            obj_type = dpath.util.get(content, f'{parent}/{type_key}')

            # convert data, and replace in dict
            dpath.util.set(content, f'{parent}/{data_key}', func(obj_type, data))

        return content

    async def _execute(self, command_type: type(commands.Command), **kwargs) -> dict:
        try:
            LOGGER.info(f'{command_type.__name__}({kwargs})')
            content = self._processed(codec.encode, kwargs)

            command = command_type().from_decoded(content)

            retval = await self._commander.execute(command)
            return self._processed(codec.decode, retval)

        except Exception as ex:
            message = f'Failed to execute {command_type()}: {type(ex).__name__}: {ex}'
            LOGGER.error(message, exc_info=True)
            raise ControllerException(message)

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

    async def object_create(self, service_id: str, obj_type: int, data: dict) -> List[int]:
        """
        Creates a new object on the controller.
        Raises exception if service_id already exists.
        """
        object = {
            self._object_store.primary_key: service_id,
            'type': obj_type,
            'data': data
        }

        await self.create_object(
            type=obj_type,
            size=18,  # TODO(Bob): fix protocol
            data=data
        )

        try:
            await self._object_store.create_by_id(service_id, object)
        except AssertionError as ex:
            # TODO(Bob): uncomment when controller id is known from create command
            # await self.delete_object(id=controller_id)
            raise ex

        return object

    async def object_read(self, service_id: str, obj_type: int=0) -> dict:
        """
        Reads state for object on controller.
        Raises exception if object does not exist.
        Returns object state.
        """
        return await self.read_value(
            id=(await resolve_controller_id(self._object_store, service_id)),
            type=obj_type,
            size=0
        )

    async def object_update(self, service_id: str, obj_type: int, data: dict) -> dict:
        """
        Updates settings for existing object.
        Raises exception if object does not exist.
        Returns new state of object.
        """
        return await self.write_value(
            id=(await resolve_controller_id(self._object_store, service_id)),
            type=obj_type,
            size=0,
            data=data
        )

    async def object_delete(self, service_id: str):
        """
        Deletes object on the controller.
        """
        return await self.delete_object(
            id=await resolve_controller_id(self._object_store, service_id)
        )

    async def object_all(self) -> dict:
        """
        Returns all known objects
        """
        return await self.list_objects(
            profile_id=self._active_profile
        )

    async def system_read(self, service_id: str) -> dict:
        """
        Reads state for system object on controller.
        Raises exception if object does not exist.
        Returns object state.
        """
        return await self.read_system_value(
            id=(await resolve_controller_id(self._system_store, service_id)),
            type=0,
            size=0
        )

    async def system_update(self, service_id: str, obj_type: int, data: dict) -> dict:
        """
        Updates settings for existing object.
        Raises exception if object does not exist.
        Returns new state of object.
        """
        return await self.write_system_value(
            id=(await resolve_controller_id(self._system_store, service_id)),
            type=obj_type,
            size=0,
            data=data
        )

    async def profile_create(self) -> dict:
        """
        Creates new profile.
        Returns id of newly created profile
        """
        return await self.create_profile()

    async def profile_delete(self, profile_id: int) -> dict:
        """
        Deletes profile.
        Raises exception if profile does not exist.
        """
        return await self.delete_profile(
            profile_id=profile_id
        )

    async def profile_activate(self, profile_id: int) -> dict:
        """
        Activates profile.
        Raises exception if profile does not exist.
        """
        retval = await self.activate_profile(
            profile_id=profile_id
        )
        self._active_profile = profile_id
        return retval

    async def alias_create(self, alias: str, controller_id: List[int]) -> dict:
        """
        Creates new alias + id combination.
        Raises exception if alias already exists.
        """
        return await self._object_store.create_by_id(alias, dict(controller_id=controller_id))

    async def alias_update(self, existing: str, new: str) -> dict:
        """
        Updates object with given alias to new alias.
        Raises exception if no object was found.
        Returns object
        """
        return await self._object_store.update_id(existing, new)
