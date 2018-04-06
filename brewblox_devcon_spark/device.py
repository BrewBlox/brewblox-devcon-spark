"""
Offers a functional interface to the device functionality
"""

import logging
from typing import List, Type

from aiohttp import web
from brewblox_codec_spark import codec
from deprecated import deprecated

from brewblox_devcon_spark import commands
from brewblox_devcon_spark.commander import SparkCommander

CONTROLLER_KEY = 'controller.spark'

LOGGER = logging.getLogger(__name__)


def get_controller(app) -> 'SparkController':
    return app[CONTROLLER_KEY]


def setup(app: Type[web.Application]):
    app[CONTROLLER_KEY] = SparkController(name=app['config']['name'], app=app)


class SparkController():
    def __init__(self, name: str, app=None):
        self._name = name
        self._commander: SparkCommander = None

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
        self._commander = SparkCommander(app.loop)
        await self._commander.bind(loop=app.loop)

    async def close(self, *args, **kwargs):
        if self._commander:
            await self._commander.close()
            self._commander = None

    @deprecated(reason='Debug function')
    async def write(self, command: str):
        LOGGER.info(f'Writing {command}')
        return await self._commander.write(command)

    @deprecated(reason='Debug function')
    async def do(self, command: str, data: dict):
        LOGGER.info(f'Doing {command}{data}')
        return await self._commander.do(command, data)

    async def _process_retval(self, retval: dict):
        obj_list_key = commands.OBJECT_LIST_KEY
        data_key = commands.OBJECT_DATA_KEY
        type_key = commands.OBJECT_TYPE_KEY

        def decode_data(parent):
            if data_key in parent:
                parent[data_key] = codec.decode(parent[type_key], parent[data_key])
            return parent

        # Check for single data items
        retval = decode_data(retval)

        # Check for lists of data
        if obj_list_key in retval:
            retval[obj_list_key] = [decode_data(obj) for obj in retval[obj_list_key] or []]

        return retval

    async def _execute(self, command: commands.Command) -> dict:
        return await self._process_retval(await self._commander.execute(command))

    async def create(self, obj_type: int, obj: dict) -> List[int]:
        """
        Creates a new object on the controller.
        Raises exception if object already exists.
        Returns ID of newly created object.
        """
        encoded = codec.encode(obj_type, obj)
        command = commands.CreateObjectCommand().from_args(
            type=obj_type,
            size=len(encoded),
            data=encoded
        )
        return await self._execute(command)

    async def read(self, id: List[int]) -> dict:
        """
        Reads state for object on controller.
        Raises exception if object does not exist.
        Returns object state.
        """
        command = commands.ReadValueCommand().from_args(
            id=id,
            type=0,
            size=0
        )
        return await self._execute(command)

    async def update(self, id: List[int], obj_type: int, obj: dict) -> dict:
        """
        (partially) updates settings for existing object.
        Raises exception if object does not exist.
        Returns new state of object.
        """
        command = commands.WriteValueCommand().from_args(
            id=id,
            type=obj_type,
            size=0,
            data=codec.encode(obj_type, obj)
        )
        return await self._execute(command)

    async def delete(self, id: List[int]):
        """
        Deletes object on the controller.
        """
        command = commands.DeleteObjectCommand().from_args(id=id)
        return await self._execute(command)

    async def all(self) -> dict:
        """
        Returns all known objects
        """
        command = commands.ListObjectsCommand().from_args(profile_id=0)
        return await self._execute(command)

    async def system_read(self, id: List[int]) -> dict:
        """
        Reads state for system object on controller.
        Raises exception if object does not exist.
        Returns object state.
        """
        command = commands.ReadSystemValueCommand().from_args(
            id=id,
            type=0,
            size=0
        )
        return await self._execute(command)

    async def system_update(self, id: List[int], obj_type: int, obj: dict) -> dict:
        """
        (partially) updates settings for existing object.
        Raises exception if object does not exist.
        Returns new state of object.
        """
        command = commands.WriteSystemValueCommand().from_args(
            id=id,
            type=obj_type,
            size=0,
            data=codec.encode(obj_type, obj)
        )
        return await self._execute(command)
