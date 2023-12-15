from contextlib import asynccontextmanager

from . import connection_handler, mqtt_connection
from .connection_handler import CV


@asynccontextmanager
async def lifespan():
    async with connection_handler.lifespan():
        yield


def setup():
    mqtt_connection.setup()
    connection_handler.setup()


__all__ = [
    'setup',
    'CV'
]
