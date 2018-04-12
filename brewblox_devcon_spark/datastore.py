"""
Offers block metadata CRUD
"""


import asyncio
from concurrent.futures import CancelledError
from datetime import timedelta
from typing import Callable, List, Any

from aiotinydb import AIOJSONStorage, AIOTinyDB
from aiotinydb.middleware import CachingMiddleware
from brewblox_devcon_spark import brewblox_logger
from tinydb import Query, Storage, operations
from deprecated import deprecated

OBJECT_TYPE_ = dict
ACTION_RETURN_TYPE_ = Any
ACTION_TIMEOUT = timedelta(seconds=10)
DATABASE_RETRY_INTERVAL = timedelta(seconds=1)

LOGGER = brewblox_logger(__name__)


class Action():

    def __init__(self, func: Callable, loop: asyncio.BaseEventLoop):
        self._future: asyncio.Future = loop.create_future()
        self._func: Callable = func

    def do(self, db):
        try:
            self._future.set_result(self._func(db))
        except Exception as ex:
            self._future.set_exception(ex)

    async def wait_result(self) -> ACTION_RETURN_TYPE_:
        return await asyncio.wait_for(self._future, timeout=ACTION_TIMEOUT.seconds)


class DataStore():

    def __init__(self,
                 file: str,
                 storage: Storage=CachingMiddleware(AIOJSONStorage),
                 primary_key='alias'):
        self._file: str = file
        self._storage: Storage = storage
        self._pk: str = primary_key

        self._pending_actions: asyncio.Queue = None
        self._runner: asyncio.Task = None
        self._loop: asyncio.BaseEventLoop = None

    def __str__(self):
        return f'<{type(self).__name__} for {self._file}>'

    async def start(self, loop: asyncio.BaseEventLoop):
        self._loop = loop
        self._pending_actions = asyncio.Queue()
        self._runner = loop.create_task(self._run())

    async def close(self):
        if self._runner:
            self._runner.cancel()
            await asyncio.wait([self._runner])

    async def _run(self):
        while True:
            try:
                async with AIOTinyDB(self._file, storage=self._storage) as db:
                    LOGGER.info(f'{self} now available')
                    while True:
                        action = await self._pending_actions.get()
                        action.do(db)

            except CancelledError:
                LOGGER.debug(f'{self} shutdown')
                break

            except Exception as ex:
                LOGGER.warn(f'{self} error: {ex}')
                # Don't go crazy on persistent errors
                await asyncio.sleep(DATABASE_RETRY_INTERVAL.seconds)

    async def _do_with_db(self, func) -> ACTION_RETURN_TYPE_:
        assert self._pending_actions is not None, f'{self} not started before functions were called'
        action = Action(func, self._loop)
        await self._pending_actions.put(action)
        return await action.wait_result()

    async def purge(self):
        return await self._do_with_db(lambda db: db.purge())

    @deprecated('Debugging function')
    async def write(self, data: dict) -> List[int]:
        return await self._do_with_db(lambda db: db.insert(data))

    @deprecated('Debugging function')
    async def all(self) -> List[OBJECT_TYPE_]:
        return await self._do_with_db(lambda db: db.all())

    async def find_by_id(self, id: str) -> List[OBJECT_TYPE_]:
        return await self._do_with_db(lambda db: db.get(Query()[self._pk] == id))

    async def create_by_id(self, id: str, obj: dict) -> OBJECT_TYPE_:
        def action_func(db, alias: str, obj: dict):
            assert not db.contains(Query()[self._pk] == id), f'{id} already exists'
            obj[self._pk] = id
            db.insert(obj)
            return obj

        return await self._do_with_db(lambda db: action_func(db, id, obj))

    async def update_id(self, existing: str, new: str) -> OBJECT_TYPE_:
        return await self._do_with_db(
            lambda db: db.update(
                operations.set(self._pk, new),
                Query()[self._pk] == existing
            )[0]
        )
