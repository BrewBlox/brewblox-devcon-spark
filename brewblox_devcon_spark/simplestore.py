"""
Straightforward multi-index dict.
Supports lookups where either left or right value is unknown.
When looking up objects with both left and right key, asserts that keys point to the same object.
"""

from typing import Any, Dict, Hashable, Tuple

from brewblox_service import brewblox_logger
from dataclasses import dataclass

LOGGER = brewblox_logger(__name__)


@dataclass(frozen=True)
class StoreObject():
    service_id: str
    controller_id: int
    remote_status: str


class MultiIndexError(Exception):
    pass


@dataclass(frozen=True)
class MultiIndexObject():
    left_key: Hashable
    right_key: Hashable
    content: Any


class IntermediateIndex():
    def __init__(self, parent: 'MultiIndexDict', left_key: Any):
        self._parent = parent
        self._left_key = left_key

    def __getitem__(self, right_key):
        return self._parent.get(self._left_key, right_key)

    def __setitem__(self, right_key, item):
        return self._parent.set(self._left_key, right_key, item)

    def __delitem__(self, right_key):
        return self._parent.delete(self._left_key, right_key)


class MultiIndexDict():
    def __init__(self):
        self._left_view: Dict[MultiIndexObject] = dict()
        self._right_view: Dict[MultiIndexObject] = dict()

    def __raise_key_missing(self, *args, **kwargs):
        raise MultiIndexError('Missing right-hand index key')

    __setitem__ = __raise_key_missing
    __delitem__ = __raise_key_missing

    def __len__(self):
        return len(self._left_view)

    def __iter__(self):
        return ((o.left_key, o.right_key, o.content) for o in self._left_view.values())

    def __getitem__(self, left_key) -> IntermediateIndex:
        return IntermediateIndex(self, left_key)

    def _getobj(self, left_key, right_key) -> MultiIndexObject:
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

    def get(self, left_key, right_key, default=None):
        try:
            return self._getobj(left_key, right_key).content
        except KeyError:
            return default

    def set(self, left_key, right_key, item):
        if (left_key, right_key) == (None, None):
            raise MultiIndexError('None/None insertion not allowed')
        left = self._left_view.get(left_key)
        right = self._right_view.get(right_key)
        if left is not right:
            raise MultiIndexError(f'Mapping mismatch: [{left_key}][{right_key}] == {left} / {right}')
        self._left_view[left_key] = self._right_view[right_key] = MultiIndexObject(left_key, right_key, item)

    def pop(self, left_key, right_key):
        obj = self._getobj(left_key, right_key)
        self._left_view.pop(obj.left_key)
        self._right_view.pop(obj.right_key)
        return obj.content

    def delete(self, left_key, right_key):
        obj = self._getobj(left_key, right_key)
        left = self._left_view.pop(obj.left_key)
        self._right_view.pop(obj.right_key)
        del left

    def __contains__(self, keys: Tuple[Hashable, Hashable]):
        left_key, right_key = keys
        try:
            self._getobj(left_key, right_key)
        except KeyError:
            return False
        else:
            return True
