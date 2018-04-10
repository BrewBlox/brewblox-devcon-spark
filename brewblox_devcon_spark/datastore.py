"""
Offers block metadata CRUD
"""


from aiohttp import web
from aiotinydb import AIOTinyDB, AIOJSONStorage
from aiotinydb.middleware import CachingMiddleware
from tinydb import Query
from async_generator import asynccontextmanager
from brewblox_devcon_spark import brewblox_logger

routes = web.RouteTableDef()

LOGGER = brewblox_logger(__name__)


DATASTORE_KEY = 'controller.datastore'


def setup(app: web.Application):
    app[DATASTORE_KEY] = DataStore(file='db.json')
    app.router.add_routes(routes)


def get_datastore(app) -> 'DataStore':
    return app[DATASTORE_KEY]


class DataStore():

    def __init__(self, file: str):
        self._file = file

    @asynccontextmanager
    async def _database(self):
        async with AIOTinyDB(self._file, storage=CachingMiddleware(AIOJSONStorage)) as db:
            yield db

    async def write(self, data: dict):
        async with self._database() as db:
            db.insert(data)

    async def find(self, alias):
        async with self._database() as db:
            block = Query()
            LOGGER.info(f'Looking for {alias}')
            return db.search(block.alias == alias)


@routes.post('/_debug/data/write')
async def write(request: web.Request) -> web.Response:
    """
    ---
    summary: Write to the datastore
    tags:
    - Debug
    - Datastore
    operationId: controller.spark.data.write
    produces:
    - application/json
    parameters:
    -
        in: body
        name: body
        description: data
        required: try
        schema:
            type: object
    """
    data = await request.json()
    await get_datastore(request.app).write(data)
    return web.json_response()


@routes.get('/_debug/data/{alias}')
async def read(request: web.Request) -> web.Response:
    """
    ---
    summary: Find data with alias
    tags:
    - Debug
    - Datastore
    operationId: controller.spark.data.find
    produces:
    - application/json
    parameters:
    -
        name: alias
        in: path
        required: true
        schema:
            type: string
    """
    alias = request.match_info['alias']
    store = get_datastore(request.app)

    return web.json_response(await store.find(alias))
