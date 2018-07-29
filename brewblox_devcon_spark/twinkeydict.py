"""
Straightforward multi-index dict.
Supports lookups where either left or right value is unknown.
When looking up objects with both left and right key, asserts that keys point to the same object.
"""

import asyncio
import json
from collections.abc import MutableMapping
from concurrent.futures import CancelledError
from contextlib import suppress
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
                 TwinKeyFileDict(app, config['database']),
                 key='object_store')
    features.add(app,
                 TwinKeyFileDict(app, config['system_database'], read_only=True),
                 key='system_store')


def get_object_store(app) -> 'TwinKeyDict':
    return features.get(app, key='object_store')


def get_system_store(app) -> 'TwinKeyDict':
    return features.get(app, key='system_store')


class TwinKeyError(Exception):
    pass


@dataclass(frozen=True)
class TwinKeyObject():
    left_key: Hashable
    right_key: Hashable
    content: Any


class TwinKeyDict(MutableMapping):
    def __init__(self, *args, **kwargs):
        self._left_view: Dict[Hashable, TwinKeyObject] = dict()
        self._right_view: Dict[Hashable, TwinKeyObject] = dict()

    def __bool__(self) -> bool:
        # TODO(Bob): brewblox/brewblox-service#90
        return True

    def __repr__(self) -> str:
        return str(self._left_view.values())

    def __len__(self) -> int:
        return len(self._left_view)

    def __iter__(self) -> Iterator[Keys_]:
        return ((o.left_key, o.right_key) for o in self._left_view.values())

    def _getobj(self, keys: Keys_) -> TwinKeyObject:
        left_key, right_key = keys

        if (left_key, right_key) == (None, None):
            raise TwinKeyError('[None, None] lookup not allowed')

        if left_key is None:
            return self._right_view[right_key]

        if right_key is None:
            return self._left_view[left_key]

        obj = self._left_view[left_key]
        if right_key != obj.right_key:
            raise TwinKeyError(f'Keys [{left_key}][{right_key}] point to different objects')
        return obj

    def __getitem__(self, keys: Keys_) -> Any:
        return self._getobj(keys).content

    def __setitem__(self, keys: Keys_, item):
        if None in keys:
            raise TwinKeyError('None keys not allowed')

        with suppress(KeyError):
            # Checks whether key combo either matches, or does not exist
            self._getobj(keys)

        left_key, right_key = keys
        obj = TwinKeyObject(left_key, right_key, item)
        self._left_view[left_key] = self._right_view[right_key] = obj

    def __delitem__(self, keys: Keys_):
        obj = self._getobj(keys)
        del self._left_view[obj.left_key]
        del self._right_view[obj.right_key]

    def left_key(self, right_key: Hashable) -> Hashable:
        return self._right_view[right_key].left_key

    def right_key(self, left_key: Hashable) -> Hashable:
        return self._left_view[left_key].right_key

    def rename(self, old_keys: Keys_, new_keys: Keys_):
        if new_keys in self:
            raise TwinKeyError(f'Already contains {new_keys}')

        obj = self._getobj(old_keys)
        new_left, new_right = new_keys
        if new_left is None:
            new_left = obj.left_key
        if new_right is None:
            new_right = obj.right_key

        try:
            del self[old_keys]
            self[new_left, new_right] = obj.content
        except TwinKeyError:  # pragma: no cover
            self[obj.left_key, obj.right_key] = obj.content


class TwinKeyFileDict(features.ServiceFeature, TwinKeyDict):
    def __init__(self, app: web.Application, filename: str, read_only: bool=False):
        features.ServiceFeature.__init__(self, app)
        TwinKeyDict.__init__(self)

        self._filename: str = filename
        self._read_only: bool = read_only
        self._flush_task: asyncio.Task = None
        self._changed_event: asyncio.Event = None

        try:
            self.read_file()
        except FileNotFoundError:
            LOGGER.warn(f'{self} file not found.')
        except Exception:
            LOGGER.error(f'{self} unable to read objects.')
            raise

    def __str__(self):
        return f'<{type(self).__name__} for {self._filename}>'

    def __setitem__(self, keys, item):
        self._check_writable()
        TwinKeyDict.__setitem__(self, keys, item)
        if self._changed_event:
            self._changed_event.set()

    def __delitem__(self, keys):
        self._check_writable()
        TwinKeyDict.__delitem__(self, keys)
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
                TwinKeyDict.__setitem__(self, obj['keys'], obj['data'])

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

    async def startup(self, app: web.Application):
        await self.shutdown(app)
        if not self._read_only:
            self._changed_event = asyncio.Event()
            self._flush_task = await scheduler.create_task(app, self._autoflush())

    async def shutdown(self, app: web.Application):
        self._changed_event = None
        await scheduler.cancel_task(app, self._flush_task)
