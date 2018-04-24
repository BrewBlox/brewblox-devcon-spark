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


class SparkController():

    def __init__(self, name: str, app=None):

        self._name = name
        self._active_profile = 0

        self._commander: SparkCommander = None
        self._object_store: FileDataStore = None
        self._system_store: FileDataStore = None
        self._object_cache: MemoryDataStore = None

        if app:
            self.setup(app)

    @property
    def name(self):
        return self._name

    @property
    def active_profile(self):
        return self._active_profile

    @active_profile.setter
    def active_profile(self, profile_id: int):
        self._active_profile = profile_id

    def setup(self, app: Type[web.Application]):
        app.on_startup.append(self.start)
        app.on_cleanup.append(self.close)

    async def start(self, app: Type[web.Application]):
        await self.close()
        config = app['config']

        self._object_cache = MemoryDataStore()
        await self._object_cache.start(loop=app.loop)

        self._object_store = FileDataStore(
            filename=config['database'],
            read_only=False
        )
        await self._object_store.start(loop=app.loop)

        self._system_store = FileDataStore(
            filename=config['system_database'],
            read_only=True
        )
        await self._system_store.start(loop=app.loop)

        self._commander = SparkCommander(app.loop)
        await self._commander.bind(
            loop=app.loop,
            device=config['device_port'],
            serial_number=config['device_id']
        )

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

    async def _data_processed(self, processor_func: Callable, content: dict) -> dict:
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
            dpath.util.set(content, f'{parent}/{data_key}', processor_func(obj_type, data))

        return content

    _data_encoded = partialmethod(_data_processed, codec.encode)
    _data_decoded = partialmethod(_data_processed, codec.decode)

    async def resolve_controller_id(self, store: DataStore, input_id: Union[str, List[int]]) -> List[int]:
        """
        Finds the controller ID matching service ID input.
        If input is a list of ints, it assumes it already is a controller ID
        """
        if isinstance(input_id, list) and all([isinstance(i, int) for i in input_id]):
            return input_id

        objects = await store.find_by_key(SERVICE_ID_KEY, input_id)
        assert objects, f'Service ID [{input_id}] not found in {store}'
        assert len(objects) == 1, f'Multiple definition of Service ID [{input_id}] found: {objects}'
        return objects[0][CONTROLLER_ID_KEY]

    async def resolve_service_id(self, store: DataStore, input_id: Union[str, List[int]]) -> str:
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
            objects = await store.find_by_key(CONTROLLER_ID_KEY, input_id)
            service_id = next(o.get(SERVICE_ID_KEY) for o in objects)
        except StopIteration:
            # If service ID not found, create alias
            service_id = '-'.join([str(i) for i in input_id])
            try:
                await store.insert_unique(
                    SERVICE_ID_KEY,
                    {
                        SERVICE_ID_KEY: service_id,
                        CONTROLLER_ID_KEY: input_id
                    }
                )
            except AssertionError:
                # We give up. Just use the raw controller ID.
                service_id = input_id

        return service_id

    async def _id_resolved(self, resolver: Callable, content: dict) -> dict:
        object_key = commands.OBJECT_ID_KEY
        system_key = commands.SYSTEM_ID_KEY

        async def resolve_key(key: str, store: DataStore):
            for path, id in dpath.util.search(content, f'**/{key}', yielded=True):
                dpath.util.set(content, path, await resolver(self, store, content[key]))

        await resolve_key(object_key, self._object_store)
        await resolve_key(system_key, self._system_store)

        return content

    _controller_id_resolved = partialmethod(_id_resolved, resolve_controller_id)
    _service_id_resolved = partialmethod(_id_resolved, resolve_service_id)

    async def _execute(self, command_type: type(commands.Command), **content) -> dict:
        try:

            # pre-processing
            for afunc in [
                self._controller_id_resolved,
                self._data_encoded,
            ]:
                content = await afunc(content)

            # execute
            retval = await self._commander.execute(
                command_type().from_decoded(content)
            )

            # post-processing
            for afunc in [
                self._service_id_resolved,
                self._data_decoded,
            ]:
                retval = await afunc(retval)

            return retval

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

    async def create_alias(self, **kwargs) -> dict:
        return await self._object_store.insert_unique(
            SERVICE_ID_KEY,
            kwargs
        )

    async def update_alias(self, existing_id: str, new_id: str) -> dict:
        return await self._object_store.update_unique(
            SERVICE_ID_KEY,
            existing_id,
            {SERVICE_ID_KEY: new_id}
        )
