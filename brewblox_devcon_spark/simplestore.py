"""
Straightforward multi-index dict.
Supports lookups where either left or right value is unknown.
When looking up objects with both left and right key, asserts that keys point to the same object.
"""

import asyncio
import json
from collections.abc import MutableMapping
from concurrent.futures import CancelledError
from typing import Any, Dict, Hashable, Tuple

import aiofiles
from aiohttp import web
from brewblox_service import brewblox_logger, features, scheduler
from dataclasses import dataclass

LOGGER = brewblox_logger(__name__)

MIN_FLUSH_INTERVAL_S = 10


def setup(app: web.Application):
    features.add(app, MultiIndexFileDict(app, app['config']['database']))


def get_store(app: web.Application):
    return features.get(app, MultiIndexFileDict)


class MultiIndexError(Exception):
    pass


@dataclass(frozen=True)
class MultiIndexObject():
    left_key: Hashable
    right_key: Hashable
    content: Any


class MultiIndexDict(MutableMapping):
    def __init__(self, *args, **kwargs):
        self._left_view: Dict[Hashable, MultiIndexObject] = dict()
        self._right_view: Dict[Hashable, MultiIndexObject] = dict()

    def __bool__(self):
        # TODO(Bob): brewblox/brewblox-service#90
        return True

    def __len__(self):
        return len(self._left_view)

    def __iter__(self):
        return ((o.left_key, o.right_key) for o in self._left_view.values())

    def _getobj(self, keys: Tuple[Hashable, Hashable]) -> Any:
        left_key, right_key = keys

        if (left_key, right_key) == (None, None):
            raise MultiIndexError('None/None lookup not allowed')

        if left_key is None:
            return self._right_view[right_key]
        elif right_key is None:
            return self._left_view[left_key]
        else:
            left = self._left_view[left_key]
            right = self._right_view[right_key]
            if left is not right:
                raise MultiIndexError(f'Keys [{left_key}][{right_key}] yielded different objects')
            return left

    def __getitem__(self, keys):
        return self._getobj(keys).content

    def __setitem__(self, keys: Tuple[Hashable, Hashable], item):
        left_key, right_key = keys
        if (left_key, right_key) == (None, None):
            raise MultiIndexError('None/None insertion not allowed')
        left = self._left_view.get(left_key)
        right = self._right_view.get(right_key)
        if left is not right:
            raise MultiIndexError(f'Mapping mismatch: [{left_key}][{right_key}] == {left} / {right}')
        self._left_view[left_key] = self._right_view[right_key] = MultiIndexObject(left_key, right_key, item)

    def __delitem__(self, keys: Tuple[Hashable, Hashable]):
        left_key, right_key = keys
        obj = self._getobj(keys)
        del self._left_view[obj.left_key]
        del self._right_view[obj.right_key]

    def bothkeys(self, keys: Tuple[Hashable, Hashable]):
        obj = self._getobj(keys)
        return obj.left_key, obj.right_key


class MultiIndexFileDict(features.ServiceFeature, MultiIndexDict):
    def __init__(self, app: web.Application, filename: str):
        features.ServiceFeature.__init__(self, app)
        MultiIndexDict.__init__(self)

        self._filename: str = filename
        self._flush_task: asyncio.Task = None
        self._flush_event: asyncio.Event = None

        try:
            self.read_file()
        except FileNotFoundError:
            LOGGER.warn(f'Unable to load objects from {self._filename}')

    def __str__(self):
        return f'<{type(self).__name__} for {self._filename}>'

    def __setitem__(self, keys, item):
        MultiIndexDict.__setitem__(self, keys, item)
        if self._flush_event:
            self._flush_event.set()

    def __delitem__(self, keys):
        MultiIndexDict.__delitem__(self, keys)
        if self._flush_event:
            self._flush_event.set()

    @property
    def active(self):
        return self._flush_task and not self._flush_task.done()

    async def startup(self, app: web.Application):
        await self.shutdown(app)
        self._flush_event = asyncio.Event()
        self._flush_task = await scheduler.create_task(app, self._autoflush())

    async def shutdown(self, app: web.Application):
        self._flush_event = None
        await scheduler.cancel_task(app, self._flush_task)

    def read_file(self):
        with open(self._filename) as f:
            persisted = json.load(f)

        for obj in persisted:
            MultiIndexDict.__setitem__(self, obj['keys'], obj['data'])

    async def write_file(self):
        persisted = [{'keys': keys, 'data': content} for keys, content in self.items()]
        async with aiofiles.open(self._filename, mode='w') as f:
            await f.write(json.dumps(persisted))
            await f.flush()

    async def _autoflush(self):
        LOGGER.info(f'Starting {self}')
        while True:
            try:
                await asyncio.sleep(MIN_FLUSH_INTERVAL_S)
                await self._flush_event.wait()
                await self.write_file()
                self._flush_event.clear()

            except CancelledError:
                await self.write_file()
                break

            except Exception as ex:
                LOGGER.warn(f'{self} {type(ex).__name__}({ex})')
                continue
