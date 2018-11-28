"""
Offers a functional interface to the device functionality
"""

import random
import string
from contextlib import suppress
from functools import partialmethod
from typing import Any, Awaitable, Callable, List, Optional, Type

from aiohttp import web
from brewblox_service import brewblox_logger, features

from brewblox_devcon_spark import (commander, commands, datastore, exceptions,
                                   twinkeydict)
from brewblox_devcon_spark.codec import codec
from brewblox_devcon_spark.commands import (OBJECT_DATA_KEY, OBJECT_ID_KEY,
                                            OBJECT_ID_LIST_KEY,
                                            OBJECT_INTERFACE_KEY,
                                            OBJECT_LIST_KEY, OBJECT_TYPE_KEY,
                                            PROFILE_LIST_KEY)

OBJECT_LINK_POSTFIX = '>'
GENERATED_ID_PREFIX = 'UNKNOWN|'
ServiceId_ = str
ControllerId_ = int
FindIdFunc_ = Callable[[twinkeydict.TwinKeyDict, Any], Awaitable[Any]]

# Keys are imported from commands for use in this module
# but also to allow other modules (eg. API) to import them from here
# "use" them here to avoid lint errors
_FORWARDED = (
    OBJECT_ID_KEY,
    OBJECT_DATA_KEY,
    OBJECT_TYPE_KEY,
    OBJECT_LIST_KEY,
    PROFILE_LIST_KEY,
    OBJECT_ID_LIST_KEY,
    OBJECT_INTERFACE_KEY,
)

LOGGER = brewblox_logger(__name__)


def get_controller(app: web.Application) -> 'SparkController':
    return features.get(app, SparkController)


def setup(app: web.Application):
    features.add(app, SparkController(name=app['config']['name'], app=app))


class SparkResolver():

    def __init__(self, app: web.Application):
        self._app = app
        self._datastore = datastore.get_datastore(app)
        self._codec = codec.get_codec(app)

    @staticmethod
    def _get_content_objects(content: dict) -> List[dict]:
        objects_to_process = [content]
        with suppress(KeyError):
            objects_to_process += content[OBJECT_LIST_KEY]
        with suppress(KeyError):
            objects_to_process += content[OBJECT_ID_LIST_KEY]
        return objects_to_process

    @staticmethod
    def _random_string():
        return GENERATED_ID_PREFIX + ''.join([
            random.choice(string.ascii_letters + string.digits)
            for n in range(32)
        ])

    async def _process_data(self,
                            codec_func: codec.TranscodeFunc_,
                            content: dict,
                            opts: Optional[dict]
                            ) -> Awaitable[dict]:
        objects_to_process = self._get_content_objects(content)

        for obj in objects_to_process:
            # transcode type + data
            with suppress(KeyError):
                new_type, new_data = await codec_func(
                    obj[OBJECT_TYPE_KEY],
                    obj[OBJECT_DATA_KEY],
                    opts=opts,
                )
                obj[OBJECT_TYPE_KEY] = new_type
                obj[OBJECT_DATA_KEY] = new_data
            # transcode interface (type only)
            with suppress(KeyError):
                new_type = await codec_func(obj[OBJECT_INTERFACE_KEY], opts=opts)
                obj[OBJECT_INTERFACE_KEY] = new_type

        return content

    def _find_controller_id(self, store: twinkeydict.TwinKeyDict, input_id: ServiceId_) -> ControllerId_:
        if not input_id:
            return 0

        if isinstance(input_id, ControllerId_):
            return input_id

        try:
            return store.right_key(input_id)
        except KeyError:
            raise exceptions.UnknownId(f'Service ID [{input_id}] not found in {store}')

    def _find_service_id(self, store: twinkeydict.TwinKeyDict, input_id: ControllerId_) -> ServiceId_:
        if not input_id:
            return None

        if isinstance(input_id, ServiceId_):
            return input_id

        try:
            service_id = store.left_key(input_id)
        except KeyError:
            # If service ID not found, randomly generate one
            service_id = SparkResolver._random_string()
            store[service_id, input_id] = dict()

        return service_id

    async def _resolve_id(self, finder_func: FindIdFunc_, content: dict) -> Awaitable[dict]:
        objects_to_process = self._get_content_objects(content)

        for obj in objects_to_process:
            with suppress(KeyError):
                obj[OBJECT_ID_KEY] = finder_func(self._datastore, obj[OBJECT_ID_KEY])

        return content

    async def _resolve_links(self,
                             finder_func: FindIdFunc_,
                             content: dict
                             ) -> Awaitable[dict]:
        store = self._datastore
        objects_to_process = self._get_content_objects(content)

        async def traverse(data):
            """Recursively finds and resolves links"""
            iter = enumerate(data) \
                if isinstance(data, (list, tuple)) \
                else data.items()

            for k, v in iter:
                if isinstance(v, (dict, list, tuple)):
                    await traverse(v)
                elif str(k).endswith(OBJECT_LINK_POSTFIX):
                    data[k] = finder_func(store, v)

        for obj in objects_to_process:
            with suppress(KeyError):
                await traverse(obj[OBJECT_DATA_KEY])

        return content

    async def encode_data(self, content: dict, opts: Optional[dict]) -> Awaitable[dict]:
        return await self._process_data(self._codec.encode, content, opts)

    async def decode_data(self, content: dict, opts: Optional[dict]) -> Awaitable[dict]:
        return await self._process_data(self._codec.decode, content, opts)

    async def resolve_controller_id(self, content: dict, _=None) -> Awaitable[dict]:
        return await self._resolve_id(self._find_controller_id, content)

    async def resolve_service_id(self, content: dict, _=None) -> Awaitable[dict]:
        return await self._resolve_id(self._find_service_id, content)

    async def resolve_controller_links(self, content: dict, _=None) -> Awaitable[dict]:
        return await self._resolve_links(self._find_controller_id, content)

    async def resolve_service_links(self, content: dict, _=None) -> Awaitable[dict]:
        return await self._resolve_links(self._find_service_id, content)


class SparkController(features.ServiceFeature):

    def __init__(self, name: str, app: web.Application):
        super().__init__(app)
        self._commander: commander.SparkCommander = None

    async def startup(self, app: web.Application):
        self._commander = commander.get_commander(app)

    async def shutdown(self, _):
        pass

    async def _execute(self,
                       command_type: Type[commands.Command],
                       command_opts: Optional[dict],
                       content_: dict = None,
                       **kwargs
                       ) -> Awaitable[dict]:
        # Allow a combination of a dict containing arguments, and loose kwargs
        content = content_ or dict()
        content.update(kwargs)

        try:
            resolver = SparkResolver(self.app)

            # pre-processing
            for afunc in [
                resolver.resolve_controller_id,
                resolver.resolve_controller_links,
                resolver.encode_data,
            ]:
                content = await afunc(content, command_opts)

            # execute
            retval = await self._commander.execute(
                command_type.from_decoded(content)
            )

            # post-processing
            for afunc in [
                resolver.decode_data,
                resolver.resolve_service_links,
                resolver.resolve_service_id,
            ]:
                retval = await afunc(retval, command_opts)

            return retval

        except Exception as ex:
            LOGGER.debug(f'Failed to execute {command_type}: {type(ex).__name__}({ex})')
            raise ex

    read_object = partialmethod(_execute, commands.ReadObjectCommand, None)
    write_object = partialmethod(_execute, commands.WriteObjectCommand, None)
    create_object = partialmethod(_execute, commands.CreateObjectCommand, None)
    delete_object = partialmethod(_execute, commands.DeleteObjectCommand, None)
    list_objects = partialmethod(_execute, commands.ListObjectsCommand, None)
    log_objects = partialmethod(_execute, commands.ListObjectsCommand, {codec.STRIP_UNLOGGED_KEY: True})
    read_stored_object = partialmethod(_execute, commands.ReadStoredObjectCommand, None)
    list_stored_objects = partialmethod(_execute, commands.ListStoredObjectsCommand, None)
    clear_objects = partialmethod(_execute, commands.ClearObjectsCommand, None)
    factory_reset = partialmethod(_execute, commands.FactoryResetCommand, None)
    reboot = partialmethod(_execute, commands.RebootCommand, None)
    list_compatible_objects = partialmethod(_execute, commands.ListCompatibleObjectsCommand, None)
    discover_objects = partialmethod(_execute, commands.DiscoverObjectsCommand, None)
