"""
Offers block metadata CRUD
"""


import asyncio
from concurrent.futures import CancelledError
from datetime import timedelta
from typing import Callable, List, Any

from aiohttp import web
from aiotinydb import AIOJSONStorage, AIOTinyDB
from aiotinydb.middleware import CachingMiddleware
from brewblox_devcon_spark import brewblox_logger
from tinydb import Query, Storage

OBJECT_TYPE_ = dict
ACTION_RETURN_TYPE_ = Any
DATASTORE_KEY = 'controller.datastore'
ACTION_TIMEOUT = timedelta(seconds=10)
DATABASE_RETRY_INTERVAL = timedelta(seconds=1)

LOGGER = brewblox_logger(__name__)


def setup(app: web.Application):
    app[DATASTORE_KEY] = DataStore(file=app['config']['database'], app=app)


def get_datastore(app) -> 'DataStore':
    return app[DATASTORE_KEY]


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
                 app: web.Application=None,
                 storage: Storage=CachingMiddleware(AIOJSONStorage)):
        self._file: str = file
        self._storage: Storage = storage

        self._pending_actions: asyncio.Queue = None
        self._runner: asyncio.Task = None
        self._loop: asyncio.BaseEventLoop = None

        if app:
            self.setup(app)

    def __str__(self):
        return f'<{type(self).__name__} for {self._file}>'

    def setup(self, app: web.Application):
        app.on_startup.append(self.start)
        app.on_cleanup.append(self.close)

    async def start(self, app):
        self._loop = app.loop
        self._pending_actions = asyncio.Queue()
        self._runner = app.loop.create_task(self._run())

    async def close(self, *args):
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

    async def write(self, data: dict) -> List[int]:
        return await self._do_with_db(lambda db: db.insert(data))

    async def find(self, alias: str) -> List[OBJECT_TYPE_]:
        block = Query()
        return await self._do_with_db(lambda db: db.search(block.alias == alias))
