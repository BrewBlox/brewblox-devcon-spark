"""
Awaitable events for tracking device and network status
"""


import asyncio
from typing import List

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
        self._issues: List[str] = []
        self._connected: asyncio.Event = None
        self._matched: asyncio.Event = None
        self._synchronized: asyncio.Event = None
        self._disconnected: asyncio.Event = None

    @property
    def is_connected(self):
        return self._connected.is_set()

    @property
    def is_matched(self):
        return self._matched.is_set()

    @property
    def is_synchronized(self):
        return self._synchronized.is_set()

    @property
    def is_disconnected(self):
        return self._disconnected.is_set()

    @property
    def state(self) -> dict:
        return {
            'connected': self._connected.is_set(),
            'matched': self._matched.is_set(),
            'synchronized': self._synchronized.is_set(),
            'issues': self._issues,
        }

    async def wait_connected(self):  # pragma: no cover
        await self._connected.wait()

    async def wait_matched(self):
        await self._matched.wait()

    async def wait_synchronized(self):
        await self._synchronized.wait()

    async def wait_disconnected(self):
        await self._disconnected.wait()

    async def on_connect(self):
        self._issues.clear()
        self._disconnected.clear()

        self._connected.set()
        if self.app['config']['skip_version_check']:  # pragma: no cover
            self._matched.set()

    async def on_matched(self):
        await self.on_connect()
        self._matched.set()

    async def on_synchronize(self):
        await self.on_matched()
        self._synchronized.set()

    async def on_disconnect(self):
        self._connected.clear()
        self._matched.clear()
        self._synchronized.clear()
        self._disconnected.set()

    def add_issues(self, issues: List[str]):
        self._issues += issues

    async def startup(self, app: web.Application):
        self._connected = asyncio.Event()
        self._matched = asyncio.Event()
        self._synchronized = asyncio.Event()
        self._disconnected = asyncio.Event()

    async def shutdown(self, app: web.Application):
        pass
