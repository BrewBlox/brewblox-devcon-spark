"""
Straightforward multi-index dict.
Supports lookups where either left or right value is unknown.
When looking up objects with both left and right key, asserts that keys point to the same object.
"""

from collections.abc import MutableMapping
from contextlib import suppress
from typing import Any, Dict, Hashable, Iterator, Tuple

from brewblox_service import brewblox_logger

from dataclasses import dataclass

Keys_ = Tuple[Hashable, Hashable]

LOGGER = brewblox_logger(__name__)


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

        left_obj, right_obj = self._left_view.get(left_key), self._right_view.get(right_key)
        if (left_obj, right_obj) == (None, None):
            raise KeyError(f'[{left_key}, {right_key}]')
        if left_obj is not right_obj:
            raise TwinKeyError(f'Keys [{left_key}, {right_key}] point to different objects')
        return left_obj

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
