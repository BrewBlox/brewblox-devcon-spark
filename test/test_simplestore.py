"""
Tests brewblox_devcon_spark.simple_store
"""

import pytest

from brewblox_devcon_spark import simplestore

TESTED = simplestore.__name__


@pytest.fixture
def store():
    return simplestore.MultiIndexDict()


@pytest.fixture
def items():
    return [
        ('left', 'right', dict()),
        (1, 2, None),
        ('same', 'same', 'twins')
    ]


def test_get_set(store, items):
    for left, right, value in items:
        store[left][right] = value

    for left, right, value in items:
        assert store[None][right] == value
        assert store[left][None] == value
        assert store[left][right] == value

        assert store.get(left, right) == value
        assert store.get(left, None) == value
        assert store.get(None, right) == value

        assert (left, right) in store
        assert (left, None) in store
        assert (None, right) in store

    assert store.get('flip', 'flop', 'default') == 'default'

    store['left']['right'] = 'update'
    assert store['left']['right'] == 'update'

    # __getitem__ mismatched keys
    with pytest.raises(simplestore.MultiIndexError):
        assert store['same']['right'] == 'no'

    # __setitem__ mismatched keys
    with pytest.raises(simplestore.MultiIndexError):
        store['left'][2] = 'mismatch'

    # get mismatched keys
    with pytest.raises(simplestore.MultiIndexError):
        store.get('left', 2)

    # set mismatched keys
    with pytest.raises(simplestore.MultiIndexError):
        store.set('left', 2, 'mismatch')

    # get None/None
    with pytest.raises(simplestore.MultiIndexError):
        assert store[None][None] == 'no'

    # set None/None
    with pytest.raises(simplestore.MultiIndexError):
        store[None][None] = 'pancakes'


def test_pop_del(store, items):
    for left, right, value in items:
        store[left][right] = value

    with pytest.raises(simplestore.MultiIndexError):
        del store['left']

    del store['left'][None]
    assert len(store) == 2
    assert store.get('left', 'right') is None
    assert ('left', 'right') not in store

    assert store.pop('same', None) == 'twins'
    with pytest.raises(KeyError):
        store.pop('same', 'same')

    assert len(store) == 1
    assert (None, 'same') not in store


def test_iterate(store, items):
    for left, right, value in items:
        store[left][right] = value

    assert len(store) == 3
    assert [(l, r, v) for l, r, v in [o for o in store]] == items
