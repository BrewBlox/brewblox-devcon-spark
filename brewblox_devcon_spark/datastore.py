"""
Stores service-related data associated with objects.
"""


from aiohttp import web
from brewblox_service import brewblox_logger, features

from brewblox_devcon_spark import twinkeydict

LOGGER = brewblox_logger(__name__)

OBJECT_ID_START = 256
SYS_OBJECTS = [
    {
        'keys': ['__sysinfo', 1],
        'data': {}
    },
    {
        'keys': ['__time', 2],
        'data': {}
    },
    {
        'keys': ['__onewirebus', 3],
        'data': {}
    },
    {
        'keys': ['__profiles', 4],
        'data': {}
    },
]


def setup(app: web.Application):
    store = twinkeydict.TwinKeyFileDict(
        app=app,
        filename=app['config']['database'],
        # System objects should not be serialized to file
        filter=lambda k, v: k[1] >= OBJECT_ID_START
    )

    features.add(app, store, key='object_store')
    add_system_objects(store)


def get_datastore(app: web.Application) -> twinkeydict.TwinKeyDict:
    return features.get(app, key='object_store')


def add_system_objects(store: twinkeydict.TwinKeyDict):
    for obj in SYS_OBJECTS:
        store[obj['keys']] = obj['data']


def clear_objects(store: twinkeydict.TwinKeyDict):
    store.clear()
    add_system_objects(store)
