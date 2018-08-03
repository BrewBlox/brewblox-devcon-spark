"""
Awaitable events for tracking device and network status
"""


import asyncio

from aiohttp import web
from brewblox_service import brewblox_logger, features

LOGGER = brewblox_logger(__name__)


def setup(app: web.Application):
    features.add(app, SparkStatus(app))


def get_status(app: web.Application) -> 'SparkStatus':
    return features.get(app, SparkStatus)


class SparkStatus(features.ServiceFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)
        self._connected: asyncio.Event = None
        self._disconnected: asyncio.Event = None

    @property
    def connected(self) -> asyncio.Event:
        return self._connected

    @property
    def disconnected(self) -> asyncio.Event:
        return self._disconnected

    async def startup(self, app: web.Application):
        self._connected = asyncio.Event()
        self._disconnected = asyncio.Event()

    async def shutdown(self, app: web.Application):
        pass
