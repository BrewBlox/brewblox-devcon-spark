"""
Offers block metadata CRUD
"""


import asyncio
from abc import abstractmethod
from collections import defaultdict
from concurrent.futures import CancelledError
from datetime import timedelta
from typing import Any, Callable, Dict, List

from aiohttp import web
from aiotinydb import AIOImmutableJSONStorage, AIOJSONStorage, AIOTinyDB
from aiotinydb.middleware import CachingMiddleware
from brewblox_service import brewblox_logger, features, scheduler
from deprecated import deprecated
from tinydb import Query, TinyDB
from tinydb.storages import MemoryStorage

ID_TYPE_ = Any
OBJECT_TYPE_ = dict
ACTION_RETURN_TYPE_ = Any
DB_FUNC_TYPE_ = Callable[[TinyDB], ACTION_RETURN_TYPE_]

ACTION_TIMEOUT = timedelta(seconds=5)
DATABASE_RETRY_INTERVAL = timedelta(seconds=1)
CONFLICT_TABLE = 'conflicts'

LOGGER = brewblox_logger(__name__)


class ConflictError(Exception):
    pass


class NotUniqueError(ConflictError):
    pass


class ConflictDetectedError(ConflictError):
    pass


def setup(app: web.Application):
    config = app['config']

    object_store = FileDataStore(
        app=app,
        filename=config['database'],
        read_only=False
    )

    system_store = FileDataStore(
        app=app,
        filename=config['system_database'],
        read_only=True
    )

    features.add(app, object_store, 'object_store')
    features.add(app, system_store, 'system_store')


def get_object_store(app) -> 'DataStore':
    return features.get(app, key='object_store')


def get_system_store(app) -> 'DataStore':
    return features.get(app, key='system_store')


class DataStore(features.ServiceFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)

    def __str__(self):
        return f'<{type(self).__name__}>'

    @abstractmethod
    async def _do_with_db(self, db_action: DB_FUNC_TYPE_) -> ACTION_RETURN_TYPE_:
        """
        Should be overridden: governs how database calls are processed.
        Various functions in DataStore supply the logic,
        while the subclasses decide how the database is provided.

        Overriding functions should behave like they called:

            return db_action(my_database)
        """
        pass  # pragma: no cover

    def _handle_conflict(self, db: TinyDB, id_key: str, id_val: ID_TYPE_):
        """
        Makes note of the newly discovered ID conflict
        Raises a NotUniqueError
        """
        conflicts = db.table(CONFLICT_TABLE)
        LOGGER.warn(f'Conflict discovered for {id_key}=={id_val}')
        conflicts.upsert({id_key: id_val}, Query()[id_key] == id_val)

        raise ConflictDetectedError(f'ID conflict for "{id_key}"=="{id_val}"')

    @deprecated('Debugging function')
    async def all(self) -> List[OBJECT_TYPE_]:
        def db_action(db: TinyDB):
            return db.all()

        return await self._do_with_db(db_action)

    async def purge(self):
        """
        Clears the entire database.
        """
        def db_action(db: TinyDB):
            db.purge_tables()

        return await self._do_with_db(db_action)

    async def find(self, id_key: str, id_val: ID_TYPE_) -> List[OBJECT_TYPE_]:
        """
        Returns all documents where document[id_key] == id_val
        """
        def db_action(db: TinyDB):
            return db.search(Query()[id_key] == id_val)

        return await self._do_with_db(db_action)

    async def insert(self, obj: dict):
        """
        Inserts document in data store. Does not verify uniqueness of any of its keys.
        """
        def db_action(db: TinyDB):
            db.insert(obj)

        return await self._do_with_db(db_action)

    async def insert_multiple(self, objects: List):
        """
        Inserts multiple documents in data store. Does not verify uniqueness.
        """
        def db_action(db: TinyDB):
            db.insert_multiple(objects)

        return await self._do_with_db(db_action)

    async def update(self, id_key: str, id_val: ID_TYPE_, obj: dict):
        """
        Replaces all documents in data store where document[id_key] == id_val.
        """
        def db_action(db: TinyDB):
            db.update(obj, Query()[id_key] == id_val)

        return await self._do_with_db(db_action)

    async def delete(self, id_key: str, id_val: ID_TYPE_):
        """
        Deletes all documents in data store where document[id_key] == id_val.
        """
        def db_action(db: TinyDB):
            db.remove(Query()[id_key] == id_val)

        return await self._do_with_db(db_action)

    async def find_unique(self, id_key: str, id_val: ID_TYPE_) -> OBJECT_TYPE_:
        """
        Returns a single document where document[id_key] == id_val.
        Raises a NotUniqueError and logs the conflict if multiple documents are found.
        """
        def db_action(db: TinyDB):
            vals = db.search(Query()[id_key] == id_val)

            if len(vals) > 1:
                self._handle_conflict(db, id_key, id_val)

            return vals[0] if vals else None

        return await self._do_with_db(db_action)

    async def insert_unique(self, id_key: str, obj: dict):
        """
        Inserts document in data store.
        Asserts that no other document has the same value for the id_key.
        Raises a NotUniqueError and logs the conflict if multiple documents are found.
        """
        def db_action(db: TinyDB):
            id = obj[id_key]

            count = db.count(Query()[id_key] == id)

            if count == 1:
                raise NotUniqueError(f'A document with {id_key}={id} already exists')

            if count > 1:
                self._handle_conflict(db, id_key, id)

            db.insert(obj)

        return await self._do_with_db(db_action)

    async def update_unique(self, id_key: str, id_val: ID_TYPE_, obj: dict):
        """
        Replaces a document in data store where document[id_key] == id_val.
        Creates new document if it did not yet exist.
        Asserts that only one document will be updated.
        Asserts that no other documents exist where document[unique_key] == obj[unique_key]
        """
        def db_action(db: TinyDB):
            old_query = (Query()[id_key] == id_val)

            if db.count(old_query) > 1:
                self._handle_conflict(db, id_key, id_val)

            if id_key in obj:
                new_id = obj[id_key]
                new_query = (Query()[id_key] == new_id)

                if id_val != new_id and db.contains(new_query):
                    raise NotUniqueError(f'A document with {id_key}={new_id} already exists')

            db.upsert(obj, old_query)

        return await self._do_with_db(db_action)

    async def known_conflicts(self) -> Dict[str, Dict[ID_TYPE_, List[OBJECT_TYPE_]]]:
        """
        Returns all conflicting items for each known conflict.

        This will not return conflicting items that have not yet been discovered (not queried).
        """
        def db_action(db: TinyDB):
            conflicts = db.table(CONFLICT_TABLE).all()
            formatted = defaultdict(dict)

            LOGGER.info(f'conflicts: {conflicts}')

            for c in conflicts:
                for id_key, id_val in c.items():
                    formatted[id_key].update({id_val: db.search(Query()[id_key] == id_val)})

            return formatted

        return await self._do_with_db(db_action)

    async def resolve_conflict(self, id_key: str, obj: dict):
        """
        Deletes all objects where document[id_key] == obj[id_key].
        Inserts obj in datastore.
        """
        def db_action(db: TinyDB):
            query = (Query()[id_key] == obj[id_key])
            db.remove(query)
            db.insert(obj)

            # Resolve the conflict
            db.table(CONFLICT_TABLE).remove(query)

        return await self._do_with_db(db_action)


class MemoryDataStore(DataStore):

    def __init__(self, app: web.Application):
        super().__init__(app)
        self._db = TinyDB(storage=CachingMiddleware(MemoryStorage))

    async def startup(self, *_):
        pass

    async def shutdown(self, *_):
        pass

    async def _do_with_db(self, db_action: DB_FUNC_TYPE_):
        return db_action(self._db)


class FileDataStore(DataStore):

    class Action():
        """
        Used for centralized file access management.
        Actions allow separation of call and result retrieval.
        """

        def __init__(self, db_action: Callable, loop: asyncio.BaseEventLoop):
            self._future: asyncio.Future = loop.create_future()
            self._db_action: Callable = db_action

        def do(self, db):
            try:
                self._future.set_result(self._db_action(db))
            except Exception as ex:
                self._future.set_exception(ex)

        async def wait_result(self) -> ACTION_RETURN_TYPE_:
            return await asyncio.wait_for(self._future, timeout=ACTION_TIMEOUT.seconds)

    ######################################################################

    def __init__(self, app: web.Application, filename: str, read_only: bool):
        super().__init__(app)

        self._filename: str = filename

        storage = AIOImmutableJSONStorage if read_only else AIOJSONStorage
        self._storage = CachingMiddleware(storage)

        self._pending_actions: asyncio.Queue = None
        self._runner: asyncio.Task = None

    def __str__(self):
        return f'<{type(self).__name__} for {self._filename}>'

    async def startup(self, app: web.Application):
        self._pending_actions = asyncio.Queue(loop=app.loop)
        self._runner = await scheduler.create_task(app, self._run())

    async def shutdown(self, *_):
        await scheduler.cancel_task(self.app, self._runner)
        self._runner = None

    # Overrides DataStore
    async def _do_with_db(self, db_action: DB_FUNC_TYPE_) -> ACTION_RETURN_TYPE_:
        if self._pending_actions is None:
            raise AssertionError(f'{self} not started before functions were called')

        action = FileDataStore.Action(db_action, self.app.loop)
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

            except Exception as ex:  # pragma: no cover
                LOGGER.warn(f'{self} {type(ex).__name__}: {ex}')
                # Don't go crazy on persistent errors
                await asyncio.sleep(DATABASE_RETRY_INTERVAL.seconds)
