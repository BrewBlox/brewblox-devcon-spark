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
from typing import Any, Callable, Dict, Hashable, Iterator, Tuple

import aiofiles
from aiohttp import web
from brewblox_service import brewblox_logger, features, scheduler
from dataclasses import dataclass

Keys_ = Tuple[Hashable, Hashable]

LOGGER = brewblox_logger(__name__)

FLUSH_DELAY_S = 5


class TwinKeyError(Exception):
    pass


@dataclass(frozen=True)
class TwinKeyObject():
    left_key: Hashable
    right_key: Hashable
    content: Any


class TwinKeyDict(MutableMapping):
    """
    Key/Key/Value mapping, supporting lookups with incomplete data.

    Left and right keys must be unique in their own set.
    (1, 2) and (2, 1) keysets can coexist, but (1, 2) and (1, 3) can't.

    The collections.abc.MutableMapping interface is fully implemented,
    giving it meaningful implementations for:
    __getitem__, __setitem__, __delitem__, __iter__, __len__, __contains__,
    __eq__, __ne__, pop, popitem, clear, update, setdefault, keys, items,
    values, get, and set.
    Additionally, the rename, left_key, and right_key functions are available.

    None is reserved as a wildcard lookup operator. Any insert must always provide both keys,
    but a __getitem__ or __contains__ call only has to specify either key.

    When two keys are provided, but they point to different objects, a TwinKeyError is raised.

    Example syntax:
        >>> twinkey = TwinKeyDict()

        # Setting and getting using both keys
        >>> twinkey['fritz', 'froggles'] = 'frabjous'
        >>> twinkey['fritz', 'froggles']
        'frabjous'

        # Partial lookup
        >>> twinkey[None, 'froggles']
        'frabjous'
        >>> ('fritz', None) in twinkey
        True

        # Getting mixed keys causes an error
        >>> twinkey[1, 2] = 4
        >>> twinkey['fritz', 2]
        Traceback (most recent call last):
        ...
        brewblox_devcon_spark.twinkeydict.TwinKeyError: Keys [fritz, 2] point to different objects

        # Using left or right key to get the other key
        >>> twinkey.right_key('fritz')
        'froggles'
        >>> twinkey.left_key('froggles')
        'fritz'

        # Iterating
        >>> for k, v in twinkey.items():
        ...    print(k, v)
        ...
        ('fritz', 'froggles') 'frabjous'
        (1, 2) 4
    """

    def __init__(self):
        self._left_view: Dict[Hashable, TwinKeyObject] = dict()
        self._right_view: Dict[Hashable, TwinKeyObject] = dict()

    def __bool__(self) -> bool:
        return bool(self._left_view)

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
            raise TwinKeyError(f'Keys [{left_key}, {right_key}] point to different objects')
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

        del self[old_keys]
        self[new_left, new_right] = obj.content


class TwinKeyFileDict(features.ServiceFeature, TwinKeyDict):
    """
    TwinKeyDict subclass to periodically flush contained objects to file.

    Will attempt to read the backing file once during __init__,
    and then add hooks to the __setitem__ and __delitem__ functions.

    Whenever an item is added or deleted, TwinKeyFileDict will flush the file a few seconds later.
    This optimizes for the scenario where data is updated in batches.
    The collection is also saved to file when the application is shut down.

    Note: modifications of objects inside the dict are not tracked.
    Calling code may choose to explicitly flush to file by calling `write_file()`.

    Example:
        >>> twinkey = TwinKeyFileDict(app, 'myfile.json')
        # Will be flushed to file
        >>> twinkey[1, 2] = {'subkey': 1}
        # Will not trigger a flush
        >>> twinkey[1, 2]['subkey'] = 2
        # Can safely be called whenever
        >>> await twinkey.write_file()
    """

    def __init__(self,
                 app: web.Application,
                 filename: str,
                 read_only: bool=False,
                 filter: Callable[[Keys_, Any], bool]=lambda k, v: True
                 ):
        features.ServiceFeature.__init__(self, app)
        TwinKeyDict.__init__(self)

        self._filename: str = filename
        self._read_only: bool = read_only
        self._filter: Callable[[Keys_, Any], bool] = filter
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
        persisted = [
            {'keys': keys, 'data': content}
            for keys, content in self.items()
            if self._filter(keys, content)
        ]
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
