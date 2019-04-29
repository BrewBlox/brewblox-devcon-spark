"""
Offers a functional interface to the device functionality
"""

import itertools
from contextlib import suppress
from functools import partialmethod
from typing import Awaitable, Callable, List, Optional, Type, Union

from aiohttp import web
from brewblox_service import brewblox_logger, features

from brewblox_devcon_spark import (commander, commands, datastore, exceptions,
                                   twinkeydict)
from brewblox_devcon_spark.codec import codec
from brewblox_devcon_spark.commands import (GROUP_LIST_KEY, OBJECT_DATA_KEY,
                                            OBJECT_ID_LIST_KEY,
                                            OBJECT_INTERFACE_KEY,
                                            OBJECT_LIST_KEY, OBJECT_NID_KEY,
                                            OBJECT_TYPE_KEY, SYSTEM_GROUP)

OBJECT_SID_KEY = 'object_sid'
OBJECT_LINK_POSTFIX_START = '<'
OBJECT_LINK_POSTFIX_END = '>'
GENERATED_ID_PREFIX = 'UNKNOWN|'
ObjectId_ = Union[str, int]
FindIdFunc_ = Callable[[twinkeydict.TwinKeyDict, ObjectId_, str], Awaitable[ObjectId_]]

# Keys are imported from commands for use in this module
# but also to allow other modules (eg. API) to import them from here
# "use" them here to avoid lint errors
_FORWARDED = (
    OBJECT_NID_KEY,
    OBJECT_DATA_KEY,
    OBJECT_TYPE_KEY,
    OBJECT_LIST_KEY,
    GROUP_LIST_KEY,
    OBJECT_ID_LIST_KEY,
    OBJECT_INTERFACE_KEY,
    SYSTEM_GROUP,
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

    def _assign_id(self, input_type: str):
        for i in itertools.count(start=1):  # pragma: no cover
            name = f'{GENERATED_ID_PREFIX}{input_type}-{i}'
            if (name, None) not in self._datastore:
                return name

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

    def _find_nid(self,
                  store: twinkeydict.TwinKeyDict,
                  sid: str,
                  input_type: str,
                  ) -> int:
        if sid is None:
            return 0

        if isinstance(sid, int):
            return sid

        try:
            return store.right_key(sid)
        except KeyError:
            raise exceptions.UnknownId(f'No numeric ID matching [sid={sid},type={input_type}] found in store')

    def _find_sid(self,
                  store: twinkeydict.TwinKeyDict,
                  nid: int,
                  input_type: str,
                  ) -> str:
        if nid is None or nid == 0:
            return None

        if isinstance(nid, str):
            raise exceptions.DecodeException(f'Expected numeric ID, got string "{nid}"')

        try:
            sid = store.left_key(nid)
        except KeyError:
            # If service ID not found, randomly generate one
            sid = self._assign_id(input_type)
            store[sid, nid] = dict()

        return sid

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
                elif str(k).endswith(OBJECT_LINK_POSTFIX_END):
                    link_type = k[k.rfind(OBJECT_LINK_POSTFIX_START)+1:-1]
                    data[k] = finder_func(store, v, link_type)

        for obj in objects_to_process:
            with suppress(KeyError):
                await traverse(obj[OBJECT_DATA_KEY])

        return content

    async def encode_data(self, content: dict, opts: Optional[dict]) -> Awaitable[dict]:
        return await self._process_data(self._codec.encode, content, opts)

    async def decode_data(self, content: dict, opts: Optional[dict]) -> Awaitable[dict]:
        return await self._process_data(self._codec.decode, content, opts)

    async def convert_sid_nid(self, content: dict, _=None) -> Awaitable[dict]:
        objects_to_process = self._get_content_objects(content)

        for obj in objects_to_process:
            # Remove the sid
            sid = obj.pop(OBJECT_SID_KEY, None)

            if sid is None or OBJECT_NID_KEY in obj:
                continue

            obj[OBJECT_NID_KEY] = self._find_nid(
                self._datastore,
                sid,
                obj.get(OBJECT_TYPE_KEY) or obj.get(OBJECT_INTERFACE_KEY))

        return content

    async def add_sid(self, content: dict, _=None) -> Awaitable[dict]:
        objects_to_process = self._get_content_objects(content)

        for obj in objects_to_process:
            # Keep the nid
            nid = obj.get(OBJECT_NID_KEY, None)

            if nid is None:
                continue

            obj[OBJECT_SID_KEY] = self._find_sid(
                self._datastore,
                nid,
                obj.get(OBJECT_TYPE_KEY) or obj.get(OBJECT_INTERFACE_KEY))

        return content

    async def convert_links_nid(self, content: dict, _=None) -> Awaitable[dict]:
        return await self._resolve_links(self._find_nid, content)

    async def convert_links_sid(self, content: dict, _=None) -> Awaitable[dict]:
        return await self._resolve_links(self._find_sid, content)


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
                resolver.convert_sid_nid,
                resolver.convert_links_nid,
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
                resolver.convert_links_sid,
                resolver.add_sid,
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
