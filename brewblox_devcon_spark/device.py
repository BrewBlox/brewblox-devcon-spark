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

        self._commander: SparkCommander = None

        self._name = name
        self._active_profile = 0

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

    async def _data_processed(self, func: Callable, content: dict) -> dict:
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

    _data_encoded = partialmethod(_data_processed, codec.encode)
    _data_decoded = partialmethod(_data_processed, codec.decode)

    async def resolve_controller_id(self, store: DataStore, input_id: Union[str, List[int]]) -> List[int]:
        if not isinstance(input_id, str):
            # No conversion required
            return input_id

        obj = await store.find_by_id(input_id)
        assert obj, f'Service ID [{input_id}] not found in {store}'
        return obj[CONTROLLER_ID_KEY]

    async def resolve_service_id(self, store: DataStore, input_id: Union[str, List[int]]) -> str:
        if isinstance(input_id, str):
            # No conversion required
            return input_id

        # If service ID not found, create alias
        service_id = '-'.join([str(i) for i in input_id])
        try:
            await self.create_alias(service_id, controller_id=input_id)
        except Exception:
            pass

        return service_id

    async def _id_resolved(self, resolver: Callable, content: dict) -> dict:
        object_key = commands.OBJECT_ID_KEY
        system_key = commands.SYSTEM_ID_KEY

        if object_key in content:
            content[object_key] = await resolver(self, self._object_store, content[object_key])

        if system_key in content:
            content[system_key] = await resolver(self, self._system_store, content[system_key])

        return content

    _controller_id_resolved = partialmethod(_id_resolved, resolve_controller_id)
    _service_id_resolved = partialmethod(_id_resolved, resolve_service_id)

    async def _execute(self, command_type: type(commands.Command), **kwargs) -> dict:
        try:

            content = await self._controller_id_resolved(
                await self._data_encoded(
                    kwargs
                )
            )

            retval = await self._commander.execute(
                command_type().from_decoded(content)
            )

            return await self._service_id_resolved(
                await self._data_decoded(
                    retval
                )
            )

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

    async def create_alias(self, service_id: str, **kwargs) -> dict:
        return await self._object_store.create_by_id(
            service_id,
            kwargs
        )

    async def update_alias(self, existing_id: str, new_id: str) -> dict:
        return await self._object_store.update_id(
            existing_id,
            new_id
        )
