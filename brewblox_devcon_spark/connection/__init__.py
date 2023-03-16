from aiohttp import web
from brewblox_service import features

from .connection_handler import ConnectionHandler
from .mqtt_connection import MqttDeviceTracker


def setup(app: web.Application):
    features.add(app, ConnectionHandler(app))
    features.add(app, MqttDeviceTracker(app))


def fget(app: web.Application) -> ConnectionHandler:
    return features.get(app, ConnectionHandler)
