"""
Offers block metadata CRUD
"""


import asyncio
from abc import ABC, abstractmethod
from concurrent.futures import CancelledError
from copy import deepcopy
from datetime import timedelta
from typing import Any, Callable, List

from aiotinydb import AIOJSONStorage, AIOTinyDB, AIOImmutableJSONStorage
from aiotinydb.middleware import CachingMiddleware
from brewblox_devcon_spark import brewblox_logger
from deprecated import deprecated
from tinydb import Query, TinyDB, operations
from tinydb.storages import MemoryStorage

OBJECT_TYPE_ = dict
ACTION_RETURN_TYPE_ = Any
DB_FUNC_TYPE_ = Callable[[TinyDB], ACTION_RETURN_TYPE_]

ACTION_TIMEOUT = timedelta(seconds=10)
DATABASE_RETRY_INTERVAL = timedelta(seconds=1)

LOGGER = brewblox_logger(__name__)


class DataStore(ABC):

    DEFAULT_PK = 'alias'

    def __init__(self, primary_key: str=DEFAULT_PK):
        self._pk: str = primary_key

    def __str__(self):
        return f'<{type(self).__name__}>'

    async def start(self, loop: asyncio.BaseEventLoop):
        """
        Implementing classes may require a startup function.
        They can (optionally) override this.
        """
        pass

    async def close(self):
        """
        Implementing classes may require a shutdown function.
        They can (optionally) override this.
        """
        pass

    @abstractmethod
    async def _do_with_db(self, func: DB_FUNC_TYPE_) -> ACTION_RETURN_TYPE_:
        """
        Should be overridden: governs how database calls are processed.
        Various functions in DataStore supply the logic,
        while the subclasses decide how the database is provided.

        Overriding functions should behave like they called:

            return func(my_database)
        """
        pass  # pragma: no cover

    @deprecated('Debugging function')
    async def write(self, data: dict) -> List[int]:
        return await self._do_with_db(lambda db: db.insert(data))

    @deprecated('Debugging function')
    async def all(self) -> List[OBJECT_TYPE_]:
        return await self._do_with_db(lambda db: db.all())

    async def purge(self):
        """
        Clears the entire database.
        """
        return await self._do_with_db(lambda db: db.purge())

    async def find_by_id(self, id: str) -> List[OBJECT_TYPE_]:
        """
        Returns the first record where `id` matches the datastore primary key.
        """
        return await self._do_with_db(lambda db: db.get(Query()[self._pk] == id))

    async def create_by_id(self, id: str, obj: dict) -> OBJECT_TYPE_:
        """
        Creates a new record with `id` as primary key.
        Raises an exception if `id` was already in use.

        Returns the newly inserted record - this includes the primary key.
        """
        def action_func(db, id: str, obj: dict):
            assert not db.contains(Query()[self._pk] == id), f'{id} already exists'
            inserted = deepcopy(obj)
            inserted[self._pk] = id
            db.insert(inserted)
            return inserted

        return await self._do_with_db(lambda db: action_func(db, id, obj))

    async def update_id(self, existing: str, new: str) -> OBJECT_TYPE_:
        """
        Updates ID of record with `existing` as ID to `new` as ID.

        Raises an exception if `existing` already is used by another record.

        Returns None if no record was updated.
        """
        def func(db):
            assert not db.get(Query()[self._pk] == id), \
                f'Unable to update [{existing}] to [{new}]: ID already exists'

            updated = db.update(
                operations.set(self._pk, new),
                Query()[self._pk] == existing
            )

            return updated[0] if updated else None

        return await self._do_with_db(func)


class MemoryDataStore(DataStore):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._db = TinyDB(storage=CachingMiddleware(MemoryStorage))

    async def _do_with_db(self, func: DB_FUNC_TYPE_):
        return func(self._db)


class FileDataStore(DataStore):

    class Action():
        """
        Used for centralized file access management.
        Actions allow separation of call and result retrieval.
        """

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

    def __init__(self, filename: str, read_only: bool, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._filename: str = filename

        storage = AIOImmutableJSONStorage if read_only else AIOJSONStorage
        self._storage = CachingMiddleware(storage)

        self._pending_actions: asyncio.Queue = None
        self._runner: asyncio.Task = None
        self._loop: asyncio.BaseEventLoop = None

    def __str__(self):
        return f'<{type(self).__name__} for {self._filename}>'

    # Overrides DataStore
    async def start(self, loop: asyncio.BaseEventLoop):
        self._loop = loop
        self._pending_actions = asyncio.Queue()
        self._runner = loop.create_task(self._run())

    # Overrides DataStore
    async def close(self):
        if self._runner:
            self._runner.cancel()
            await asyncio.wait([self._runner])
            self._runner = None

    # Overrides DataStore
    async def _do_with_db(self, func: DB_FUNC_TYPE_) -> ACTION_RETURN_TYPE_:
        assert self._pending_actions is not None, f'{self} not started before functions were called'
        action = FileDataStore.Action(func, self._loop)
        await self._pending_actions.put(action)
        return await action.wait_result()

    async def _run(self):
        while True:
            try:
                async with AIOTinyDB(self._filename, storage=CachingMiddleware(AIOJSONStorage)) as db:
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
