"""
Awaitable events for tracking device and network status
"""


import asyncio
import warnings
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
        self._address: str = None
        self._info: List[str] = []
        self._compatible: bool = True  # until proven otherwise
        self._latest: bool = True
        self._connect_ev: asyncio.Event = None
        self._handshake_ev: asyncio.Event = None
        self._synchronize_ev: asyncio.Event = None
        self._disconnect_ev: asyncio.Event = None

    @property
    def is_connected(self):
        return self._connect_ev.is_set()

    @property
    def is_compatible(self):
        return self._compatible

    @property
    def is_synchronized(self):
        return self._synchronize_ev.is_set()

    @property
    def is_disconnected(self):
        return self._disconnect_ev.is_set()

    @property
    def address(self):
        return self._address

    @property
    def info(self):
        return self._info

    @info.setter
    def info(self, new_vals):
        self._info = new_vals.copy()

    @property
    def state(self) -> dict:
        return {
            'connect': self._connect_ev.is_set(),
            'handshake': self._handshake_ev.is_set(),
            'synchronize': self._synchronize_ev.is_set(),
            'compatible': self._compatible,
            'latest': self._latest,
            'info': self._info,
        }

    async def wait_connect(self):
        await self._connect_ev.wait()

    async def wait_handshake(self):
        await self._handshake_ev.wait()

    async def wait_synchronize(self):
        await self._synchronize_ev.wait()

    async def wait_disconnect(self):
        await self._disconnect_ev.wait()

    async def on_connect(self, address: str):
        self._address = address
        self._disconnect_ev.clear()
        self._connect_ev.set()

    async def on_handshake(self, compatible: bool, latest: bool):
        self._compatible = self.app['config']['skip_version_check'] or compatible
        self._latest = latest

        self._handshake_ev.set()

        if not compatible:
            self._synchronize_ev.clear()
            warnings.warn('Handshake failed: firmware incompatible')

    async def on_synchronize(self):
        self._synchronize_ev.set()

    async def on_disconnect(self):
        self._info = []
        self._connect_ev.clear()
        self._handshake_ev.clear()
        self._synchronize_ev.clear()
        self._disconnect_ev.set()

    async def startup(self, app: web.Application):
        self._connect_ev = asyncio.Event()
        self._handshake_ev = asyncio.Event()
        self._synchronize_ev = asyncio.Event()
        self._disconnect_ev = asyncio.Event()

    async def shutdown(self, app: web.Application):
        pass
