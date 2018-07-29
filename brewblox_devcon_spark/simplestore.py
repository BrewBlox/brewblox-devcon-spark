"""
Straightforward multi-index dict.
Supports lookups where either left or right value is unknown.
When looking up objects with both left and right key, asserts that keys point to the same object.
"""

import asyncio
import json
from collections.abc import MutableMapping
from concurrent.futures import CancelledError
from typing import Any, Dict, Hashable, Iterator, Tuple

import aiofiles
from aiohttp import web
from brewblox_service import brewblox_logger, features, scheduler
from dataclasses import dataclass

Keys_ = Tuple[Hashable, Hashable]

LOGGER = brewblox_logger(__name__)

FLUSH_DELAY_S = 5


def setup(app: web.Application):
    config = app['config']
    features.add(app,
                 MultiIndexFileDict(app, config['database']),
                 key='simple_object_store')

    features.add(app,
                 MultiIndexFileDict(app, config['system_database'], read_only=True),
                 key='simple_system_store')


def get_object_store(app) -> 'MultiIndexDict':
    return features.get(app, key='simple_object_store')


def get_system_store(app) -> 'MultiIndexDict':
    return features.get(app, key='simple_system_store')


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

    def __bool__(self) -> bool:
        # TODO(Bob): brewblox/brewblox-service#90
        return True

    def __len__(self) -> int:
        return len(self._left_view)

    def __iter__(self) -> Iterator[Keys_]:
        return ((o.left_key, o.right_key) for o in self._left_view.values())

    def _getobj(self, keys: Keys_) -> MultiIndexObject:
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

    def __getitem__(self, keys: Keys_) -> Any:
        return self._getobj(keys).content

    def __setitem__(self, keys: Keys_, item):
        left_key, right_key = keys
        if left_key is None or right_key is None:
            raise MultiIndexError('None keys not allowed')

        left = self._left_view.get(left_key)
        right = self._right_view.get(right_key)
        if left is not right:
            raise MultiIndexError(f'Mapping mismatch on existing items: {left} / {right}')

        obj = MultiIndexObject(left_key, right_key, item)
        self._left_view[left_key] = obj
        self._right_view[right_key] = obj

    def __delitem__(self, keys: Keys_):
        left_key, right_key = keys
        obj = self._getobj(keys)
        del self._left_view[obj.left_key]
        del self._right_view[obj.right_key]

    def left_key(self, right_key: Hashable) -> Hashable:
        return self._right_view[right_key].left_key

    def right_key(self, left_key: Hashable) -> Hashable:
        return self._left_view[left_key].right_key

    def rename(self, keys: Keys_, new_keys: Keys_):
        if new_keys in self:
            raise MultiIndexError(f'Already contains {new_keys}')

        obj = self._getobj(keys)
        left, right = new_keys
        left = left if left is not None else obj.left_key
        right = right if right is not None else obj.right_key

        try:
            del self[keys]
            self[left, right] = obj.content
        except MultiIndexError:  # pragma: no cover
            self[obj.left_key, obj.right_key] = obj.content


class MultiIndexFileDict(features.ServiceFeature, MultiIndexDict):
    def __init__(self, app: web.Application, filename: str, read_only: bool=False):
        features.ServiceFeature.__init__(self, app)
        MultiIndexDict.__init__(self)

        self._filename: str = filename
        self._read_only: bool = read_only
        self._flush_task: asyncio.Task = None
        self._changed_event: asyncio.Event = None

        try:
            self.read_file()
        except FileNotFoundError:
            LOGGER.warn(f'{self} file not found.')
            pass
        except Exception:
            LOGGER.error(f'{self} unable to read objects.')
            raise

    def __str__(self):
        return f'<{type(self).__name__} for {self._filename}>'

    def __setitem__(self, keys, item):
        self._check_writable()
        MultiIndexDict.__setitem__(self, keys, item)
        if self._changed_event:
            self._changed_event.set()

    def __delitem__(self, keys):
        self._check_writable()
        MultiIndexDict.__delitem__(self, keys)
        if self._changed_event:
            self._changed_event.set()

    @property
    def active(self):
        return self._flush_task and not self._flush_task.done()

    def _check_writable(self):
        if self._read_only:
            raise TypeError(f'{self} is read-only')

    def read_file(self):
        with open(self._filename) as f:
            for obj in json.load(f):
                MultiIndexDict.__setitem__(self, obj['keys'], obj['data'])

    async def write_file(self):
        self._check_writable()
        persisted = [{'keys': keys, 'data': content} for keys, content in self.items()]
        async with aiofiles.open(self._filename, mode='w') as f:
            await f.write(json.dumps(persisted))

    async def _autoflush(self):
        while True:
            try:
                await self._changed_event.wait()
                await asyncio.sleep(FLUSH_DELAY_S)
                await self.write_file()
                self._changed_event.clear()

            except CancelledError:
                await self.write_file()
                break

            except Exception as ex:
                LOGGER.warn(f'{self} {type(ex).__name__}({ex})')
                continue

    async def startup(self, app: web.Application):
        await self.shutdown(app)
        if not self._read_only:
            self._changed_event = asyncio.Event()
            self._flush_task = await scheduler.create_task(app, self._autoflush())

    async def shutdown(self, app: web.Application):
        self._changed_event = None
        await scheduler.cancel_task(app, self._flush_task)
