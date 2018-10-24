"""
Stores service-related data associated with objects.
"""


from aiohttp import web
from brewblox_service import brewblox_logger, features

from brewblox_devcon_spark import file_config, twinkeydict

LOGGER = brewblox_logger(__name__)

OBJECT_ID_START = 100
SYS_OBJECTS = [
    {'keys': keys, 'data': {}}
    for keys in [
        ['__profiles', 1],
        ['__sysinfo', 2],
        ['__time', 3],
        ['__onewirebus', 4],
        # Spark V3
        ['__pin_bottom_1', 10],
        ['__pin_bottom_2', 11],
        ['__pin_top_1', 12],
        ['__pin_top_2', 13],
        ['__pin_top_3', 14],
        # Spark V1/V2
        ['__actuator_0', 15],
        ['__actuator_1', 16],
        ['__actuator_2', 17],
        ['__actuator_3', 18],
    ]
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

    config = file_config.FileConfig(app, app['config']['config'])
    features.add(app, config)


def get_datastore(app: web.Application) -> twinkeydict.TwinKeyDict:
    return features.get(app, key='object_store')


def add_system_objects(store: twinkeydict.TwinKeyDict):
    for obj in SYS_OBJECTS:
        store[obj['keys']] = obj['data']


def clear_objects(store: twinkeydict.TwinKeyDict):
    store.clear()
    add_system_objects(store)


def get_config(app: web.Application) -> file_config.FileConfig:
    return features.get(app, file_config.FileConfig)
