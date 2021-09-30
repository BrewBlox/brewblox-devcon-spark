"""
Offers a functional interface to the device functionality
"""

import asyncio
import itertools
import re
from contextlib import suppress
from copy import deepcopy
from functools import partialmethod
from typing import Awaitable, Callable, Type, Union

from aiohttp import web
from brewblox_service import brewblox_logger, features, strex

from brewblox_devcon_spark import (block_store, codec, commander, commands,
                                   const, exceptions, service_status,
                                   twinkeydict)
from brewblox_devcon_spark.codec import (DecodeOpts, FilterOpt, MetadataOpt,
                                         ProtoEnumOpt)

ObjectId_ = Union[str, int]
FindIdFunc_ = Callable[[twinkeydict.TwinKeyDict, ObjectId_, str], Awaitable[ObjectId_]]

LOGGER = brewblox_logger(__name__)


class SparkResolver():

    def __init__(self, app: web.Application):
        self._app = app
        self._name = app['config']['name']
        self._store = block_store.fget(app)
        self._codec = codec.fget(app)

    @staticmethod
    def _get_content_objects(content: dict) -> list[dict]:
        objects_to_process = [content]
        with suppress(KeyError):
            objects_to_process += content['objects']
        with suppress(KeyError):
            objects_to_process += content['object_ids']
        return objects_to_process

    def _assign_id(self, input_type: str):
        clean_name = re.sub(r',driven', '', input_type)
        for i in itertools.count(start=1):  # pragma: no cover
            name = f'{const.GENERATED_ID_PREFIX}{clean_name}-{i}'
            if (name, None) not in self._store:
                return name

    async def _process_data(self,
                            codec_func: codec.TranscodeFunc_,
                            content: dict,
                            **kwargs
                            ) -> dict:
        for obj in self._get_content_objects(content):
            # transcode type + data
            with suppress(KeyError):
                new_type, new_data = await codec_func(
                    obj['type'],
                    obj['data'],
                    **kwargs,
                )
                obj['type'] = new_type
                obj['data'] = new_data
            # transcode interface (type only)
            with suppress(KeyError):
                new_type = await codec_func(obj['interface'], **kwargs)
                obj['interface'] = new_type

        return content

    def _find_nid(self,
                  store: twinkeydict.TwinKeyDict,
                  sid: str,
                  input_type: str,
                  ) -> int:
        if sid is None:
            return 0

        if isinstance(sid, int) or sid.isdigit():
            return int(sid)

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
                             ) -> dict:
        async def traverse(data):
            """Recursively finds and resolves links"""
            iter = enumerate(data) \
                if isinstance(data, (list, tuple)) \
                else data.items()

            for k, v in iter:
                if isinstance(v, dict):
                    if v.get('__bloxtype', None) == 'Link':
                        v['id'] = finder_func(self._store, v['id'], v.get('type'))
                    else:
                        await traverse(v)
                elif isinstance(v, (list, tuple)):
                    await traverse(v)
                elif str(k).endswith(const.OBJECT_LINK_POSTFIX_END):
                    link_type = k[k.rfind(const.OBJECT_LINK_POSTFIX_START)+1:-1]
                    data[k] = finder_func(self._store, v, link_type)

        for obj in self._get_content_objects(content):
            with suppress(KeyError):
                await traverse(obj['data'])

        return content

    async def encode_data(self, content: dict) -> dict:
        return await self._process_data(self._codec.encode, content)

    async def decode_data(self, content: dict, opts: DecodeOpts) -> dict:
        return await self._process_data(self._codec.decode, content, opts=opts)

    async def convert_sid_nid(self, content: dict) -> dict:
        for obj in self._get_content_objects(content):
            # Remove the sid
            sid = obj.pop('id', None)

            if sid is None or 'nid' in obj:
                continue

            obj['nid'] = self._find_nid(
                self._store,
                sid,
                obj.get('type') or obj.get('interface'))

        return content

    async def add_sid(self, content: dict) -> dict:
        for obj in self._get_content_objects(content):
            # Keep the nid
            nid = obj.get('nid', None)

            if nid is None:
                continue

            obj['id'] = self._find_sid(
                self._store,
                nid,
                obj.get('type') or obj.get('interface'))

        return content

    async def convert_links_nid(self, content: dict) -> dict:
        return await self._resolve_links(self._find_nid, content)

    async def convert_links_sid(self, content: dict) -> dict:
        return await self._resolve_links(self._find_sid, content)

    async def add_service_id(self, content: dict) -> dict:
        for obj in self._get_content_objects(content):
            obj['serviceId'] = self._name

        return content


class SparkController(features.ServiceFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)

    async def startup(self, app: web.Application):
        self._conn_check_lock = asyncio.Lock()

    async def validate(self, content_: dict = None, **kwargs) -> dict:
        content = content_ or dict()
        content.update(kwargs)
        opts = DecodeOpts()

        resolver = SparkResolver(self.app)

        content = await resolver.convert_sid_nid(content)
        content = await resolver.convert_links_nid(content)
        content = await resolver.encode_data(content)
        content = await resolver.decode_data(content, opts)
        content = await resolver.convert_links_sid(content)
        content = await resolver.add_sid(content)

        return content

    async def check_connection(self):
        """
        Sends a Noop command to controller to evaluate the connection.
        If this command also fails, prompt the commander to reconnect.

        Only do this when the service is synchronized,
        to avoid weird interactions when prompting for a handshake.
        """
        async with self._conn_check_lock:
            if await service_status.wait_synchronized(self.app, wait=False):
                LOGGER.info('Checking connection...')
                cmder = commander.fget(self.app)
                try:
                    cmd = commands.NoopCommand.from_args()
                    await cmder.execute(cmd)
                except Exception:
                    await cmder.start_reconnect()

    async def _execute(self,
                       command_type: Type[commands.Command],
                       decode_opts: list[DecodeOpts],
                       content_: dict = None,
                       /,
                       **kwargs
                       ) -> Union[dict, list[dict]]:
        # Allow a combination of a dict containing arguments, and loose kwargs
        content = (content_ or dict()) | kwargs

        cmder = commander.fget(self.app)
        resolver = SparkResolver(self.app)

        if await service_status.wait_updating(self.app, wait=False):
            raise exceptions.UpdateInProgress('Update is in progress')

        try:
            # pre-processing
            content = await resolver.convert_sid_nid(content)
            content = await resolver.convert_links_nid(content)
            content = await resolver.encode_data(content)

            # execute
            command_retval = await cmder.execute(
                command_type.from_decoded(content)
            )

            # post-processing
            output: list[dict] = []

            for opts in decode_opts:
                retval = deepcopy(command_retval)
                retval = await resolver.decode_data(retval, opts)
                retval = await resolver.convert_links_sid(retval)
                retval = await resolver.add_sid(retval)
                retval = await resolver.add_service_id(retval)
                output.append(retval)

            # Multiple decoding opts is the exception
            # Don't unnecessarily wrap the output
            if len(decode_opts) == 1:
                return output[0]
            else:
                return output

        except exceptions.CommandTimeout as ex:
            # Wrap in a task to not delay the original response
            asyncio.create_task(self.check_connection())
            raise ex

        except Exception as ex:
            LOGGER.debug(f'Failed to execute {command_type}: {strex(ex)}')
            raise ex

    default_decode_opts = DecodeOpts()
    stored_decode_opts = DecodeOpts(enums=ProtoEnumOpt.INT)
    logged_decode_opts = DecodeOpts(enums=ProtoEnumOpt.INT,
                                    filter=FilterOpt.LOGGED,
                                    metadata=MetadataOpt.POSTFIX)

    noop = partialmethod(_execute, commands.NoopCommand, [default_decode_opts])
    read_object = partialmethod(_execute, commands.ReadObjectCommand, [default_decode_opts])
    read_logged_object = partialmethod(_execute, commands.ReadObjectCommand, [logged_decode_opts])
    read_stored_object = partialmethod(_execute, commands.ReadStoredObjectCommand, [stored_decode_opts])
    write_object = partialmethod(_execute, commands.WriteObjectCommand, [default_decode_opts])
    create_object = partialmethod(_execute, commands.CreateObjectCommand, [default_decode_opts])
    delete_object = partialmethod(_execute, commands.DeleteObjectCommand, [default_decode_opts])
    list_objects = partialmethod(_execute, commands.ListObjectsCommand, [default_decode_opts])
    list_logged_objects = partialmethod(_execute, commands.ListObjectsCommand, [logged_decode_opts])
    list_stored_objects = partialmethod(_execute, commands.ListStoredObjectsCommand, [stored_decode_opts])
    list_broadcast_objects = partialmethod(_execute, commands.ListObjectsCommand,
                                           [default_decode_opts, logged_decode_opts])
    clear_objects = partialmethod(_execute, commands.ClearObjectsCommand, [default_decode_opts])
    factory_reset = partialmethod(_execute, commands.FactoryResetCommand, [default_decode_opts])
    reboot = partialmethod(_execute, commands.RebootCommand, [default_decode_opts])
    list_compatible_objects = partialmethod(_execute, commands.ListCompatibleObjectsCommand, [default_decode_opts])
    discover_objects = partialmethod(_execute, commands.DiscoverObjectsCommand, [default_decode_opts])


def setup(app: web.Application):
    features.add(app, SparkController(app))


def fget(app: web.Application) -> SparkController:
    return features.get(app, SparkController)
