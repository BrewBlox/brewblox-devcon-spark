"""
Offers a functional interface to the device functionality
"""

from typing import List, Type

from aiohttp import web
from brewblox_codec_spark import codec
from brewblox_devcon_spark import brewblox_logger, commands
from brewblox_devcon_spark.commander import SparkCommander
from brewblox_devcon_spark.datastore import DataStore, FileDataStore, MemoryDataStore
from deprecated import deprecated

CONTROLLER_KEY = 'controller.spark'
SERVICE_ID_KEY = 'service_id'
CONTROLLER_ID_KEY = 'controller_id'

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
        if self._commander:
            await self._commander.close()
            self._commander = None

        [
            await s.close() for s in [
                self._object_store,
                self._object_cache,
                self._system_store
            ]
            if s is not None
        ]

    @deprecated(reason='Debug function')
    async def write(self, command: str):
        LOGGER.info(f'Writing {command}')
        return await self._commander.write(command)

    @deprecated(reason='Debug function')
    async def do(self, command: str, data: dict):
        LOGGER.info(f'Doing {command}{data}')
        return await self._commander.do(command, data)

    async def _process_retval(self, retval: dict) -> dict:
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
        try:
            return await self._process_retval(await self._commander.execute(command))
        except Exception as ex:
            message = f'Failed to execute {command}: {type(ex).__name__}: {ex}'
            LOGGER.error(message)
            raise ControllerException(message)

    async def _resolve_controller_id(self, store: DataStore, input_id: str) -> List[int]:
        obj = await store.find_by_id(input_id)
        assert obj, f'Service ID [{input_id}] not found in {store}'
        return obj[CONTROLLER_ID_KEY]

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

        # object.update()

        command = commands.CreateObjectCommand().from_args(
            type=obj_type,
            size=18,  # TODO(Bob): fix protocol
            data=codec.encode(obj_type, data)
        )
        # TODO(Bob): update object with values returned from create
        await self._execute(command)

        try:
            await self._object_store.create_by_id(service_id, object)
        except AssertionError as ex:
            # TODO(Bob): uncomment when controller id is known from create command
            # rollback_command = commands.DeleteObjectCommand().from_args(
            #     id=controller_id
            # )
            # await self._execute(rollback_command)
            raise ex

        return object

    async def object_read(self, service_id: str, obj_type: int=0) -> dict:
        """
        Reads state for object on controller.
        Raises exception if object does not exist.
        Returns object state.
        """
        command = commands.ReadValueCommand().from_args(
            id=(await self._resolve_controller_id(self._object_store, service_id)),
            type=obj_type,
            size=0
        )
        return await self._execute(command)

    async def object_update(self, service_id: str, obj_type: int, data: dict) -> dict:
        """
        Updates settings for existing object.
        Raises exception if object does not exist.
        Returns new state of object.
        """
        command = commands.WriteValueCommand().from_args(
            id=(await self._resolve_controller_id(self._object_store, service_id)),
            type=obj_type,
            size=0,
            data=codec.encode(obj_type, data)
        )
        return await self._execute(command)

    async def object_delete(self, service_id: str):
        """
        Deletes object on the controller.
        """
        command = commands.DeleteObjectCommand().from_args(
            id=await self._resolve_controller_id(self._object_store, service_id)
        )
        return await self._execute(command)

    async def object_all(self) -> dict:
        """
        Returns all known objects
        """
        command = commands.ListObjectsCommand().from_args(
            profile_id=self._active_profile
        )
        return await self._execute(command)

    async def system_read(self, service_id: str) -> dict:
        """
        Reads state for system object on controller.
        Raises exception if object does not exist.
        Returns object state.
        """
        command = commands.ReadSystemValueCommand().from_args(
            id=(await self._resolve_controller_id(self._system_store, service_id)),
            type=0,
            size=0
        )
        return await self._execute(command)

    async def system_update(self, service_id: str, obj_type: int, data: dict) -> dict:
        """
        Updates settings for existing object.
        Raises exception if object does not exist.
        Returns new state of object.
        """
        command = commands.WriteSystemValueCommand().from_args(
            id=(await self._resolve_controller_id(self._system_store, service_id)),
            type=obj_type,
            size=0,
            data=codec.encode(obj_type, data)
        )
        return await self._execute(command)

    async def profile_create(self) -> dict:
        """
        Creates new profile.
        Returns id of newly created profile
        """
        command = commands.CreateProfileCommand().from_args()
        return await self._execute(command)

    async def profile_delete(self, profile_id: int) -> dict:
        """
        Deletes profile.
        Raises exception if profile does not exist.
        """
        command = commands.DeleteProfileCommand().from_args(
            profile_id=profile_id
        )
        return await self._execute(command)

    async def profile_activate(self, profile_id: int) -> dict:
        """
        Activates profile.
        Raises exception if profile does not exist.
        """
        command = commands.ActivateProfileCommand().from_args(
            profile_id=profile_id
        )
        retval = await self._execute(command)
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
