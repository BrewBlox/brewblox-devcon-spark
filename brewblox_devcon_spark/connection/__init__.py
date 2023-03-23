from aiohttp import web

from . import connection_handler, mqtt_connection


def setup(app: web.Application):
    mqtt_connection.setup(app)
    connection_handler.setup(app)


def fget(app: web.Application):
    return connection_handler.fget(app)
