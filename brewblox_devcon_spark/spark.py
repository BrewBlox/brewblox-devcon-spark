"""
Offers a functional interface to the device functionality
"""

import asyncio
import itertools
import re
from contextlib import suppress
from functools import partialmethod
from typing import Awaitable, Callable, List, Type, Union

from aiohttp import web
from brewblox_service import brewblox_logger, features, strex

from brewblox_devcon_spark import (block_store, codec, commander, commands,
                                   const, exceptions, service_status,
                                   twinkeydict)
from brewblox_devcon_spark.codec import (CodecOpts, FilterOpt, MetadataOpt,
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
    def _get_content_objects(content: dict) -> List[dict]:
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
                            opts: CodecOpts
                            ) -> dict:
        for obj in self._get_content_objects(content):
            # transcode type + data
            with suppress(KeyError):
                new_type, new_data = await codec_func(
                    obj['type'],
                    obj['data'],
                    opts=opts,
                )
                obj['type'] = new_type
                obj['data'] = new_data
            # transcode interface (type only)
            with suppress(KeyError):
                new_type = await codec_func(obj['interface'], opts=opts)
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

    async def encode_data(self, content: dict, opts: CodecOpts) -> dict:
        return await self._process_data(self._codec.encode, content, opts)

    async def decode_data(self, content: dict, opts: CodecOpts) -> dict:
        return await self._process_data(self._codec.decode, content, opts)

    async def convert_sid_nid(self, content: dict, opts: CodecOpts) -> dict:
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

    async def add_sid(self, content: dict, opts: CodecOpts) -> dict:
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

    async def convert_links_nid(self, content: dict, opts: CodecOpts) -> dict:
        return await self._resolve_links(self._find_nid, content)

    async def convert_links_sid(self, content: dict, opts: CodecOpts) -> dict:
        return await self._resolve_links(self._find_sid, content)

    async def add_service_id(self, content: dict, opts: CodecOpts) -> dict:
        for obj in self._get_content_objects(content):
            obj['serviceId'] = self._name

        return content


class SparkController(features.ServiceFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)

    async def startup(self, app: web.Application):
        self._conn_check_lock = asyncio.Lock()

    async def shutdown(self, _):
        pass

    async def validate(self, content_: dict = None, **kwargs) -> dict:
        content = content_ or dict()
        content.update(kwargs)
        opts = CodecOpts()

        resolver = SparkResolver(self.app)

        for afunc in [
            resolver.convert_sid_nid,
            resolver.convert_links_nid,
            resolver.encode_data,
            resolver.decode_data,
            resolver.convert_links_sid,
            resolver.add_sid,
        ]:
            content = await afunc(content, opts)

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
                       command_opts: CodecOpts,
                       content_: dict = None,
                       **kwargs
                       ) -> dict:
        # Allow a combination of a dict containing arguments, and loose kwargs
        content = content_ or dict()
        content.update(kwargs)

        cmder = commander.fget(self.app)
        resolver = SparkResolver(self.app)

        if await service_status.wait_updating(self.app, wait=False):
            raise exceptions.UpdateInProgress('Update is in progress')

        try:
            # pre-processing
            for afunc in [
                resolver.convert_sid_nid,
                resolver.convert_links_nid,
                resolver.encode_data,
            ]:
                content = await afunc(content, command_opts)

            # execute
            retval = await cmder.execute(
                command_type.from_decoded(content)
            )

            # post-processing
            for afunc in [
                resolver.decode_data,
                resolver.convert_links_sid,
                resolver.add_sid,
                resolver.add_service_id,
            ]:
                retval = await afunc(retval, command_opts)

            return retval

        except asyncio.CancelledError:  # pragma: no cover
            raise

        except exceptions.CommandTimeout as ex:
            # Wrap in a task to not delay the original response
            asyncio.create_task(self.check_connection())
            raise ex

        except Exception as ex:
            LOGGER.debug(f'Failed to execute {command_type}: {strex(ex)}')
            raise ex

    default_call_opts = CodecOpts()
    stored_call_opts = CodecOpts(enums=ProtoEnumOpt.INT)
    logged_call_opts = CodecOpts(enums=ProtoEnumOpt.INT,
                                 filter=FilterOpt.LOGGED,
                                 metadata=MetadataOpt.POSTFIX)

    noop = partialmethod(_execute, commands.NoopCommand, default_call_opts)
    read_object = partialmethod(_execute, commands.ReadObjectCommand, default_call_opts)
    read_logged_object = partialmethod(_execute, commands.ReadObjectCommand, logged_call_opts)
    read_stored_object = partialmethod(_execute, commands.ReadStoredObjectCommand, stored_call_opts)
    write_object = partialmethod(_execute, commands.WriteObjectCommand, default_call_opts)
    create_object = partialmethod(_execute, commands.CreateObjectCommand, default_call_opts)
    delete_object = partialmethod(_execute, commands.DeleteObjectCommand, default_call_opts)
    list_objects = partialmethod(_execute, commands.ListObjectsCommand, default_call_opts)
    list_logged_objects = partialmethod(_execute, commands.ListObjectsCommand, logged_call_opts)
    list_stored_objects = partialmethod(_execute, commands.ListStoredObjectsCommand, stored_call_opts)
    clear_objects = partialmethod(_execute, commands.ClearObjectsCommand, default_call_opts)
    factory_reset = partialmethod(_execute, commands.FactoryResetCommand, default_call_opts)
    reboot = partialmethod(_execute, commands.RebootCommand, default_call_opts)
    list_compatible_objects = partialmethod(_execute, commands.ListCompatibleObjectsCommand, default_call_opts)
    discover_objects = partialmethod(_execute, commands.DiscoverObjectsCommand, default_call_opts)


def setup(app: web.Application):
    features.add(app, SparkController(app))


def fget(app: web.Application) -> SparkController:
    return features.get(app, SparkController)
