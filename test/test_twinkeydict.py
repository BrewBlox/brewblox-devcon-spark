"""
Tests brewblox_devcon_spark.simple_store
"""


import pytest

from brewblox_devcon_spark import twinkeydict

TESTED = twinkeydict.__name__


@pytest.fixture
def items():
    return [
        ('left', 'right', dict()),
        (1, 2, None),
        ('same', 'same', 'twins')
    ]


@pytest.fixture
def store():
    return twinkeydict.TwinKeyDict()


def test_get_set(store, items):
    assert not store
    store['tri', 'ang'] = 'le'
    assert store

    for left, right, value in items:
        store[left, right] = value

    for left, right, value in items:
        assert store[None, right] == value
        assert store[left, None] == value
        assert store[left, right] == value

        assert store.get((left, right)) == value
        assert store.get((left, None)) == value
        assert store.get((None, right)) == value

        assert (left, right) in store
        assert (left, None) in store
        assert (None, right) in store

    assert store.get(('flip', 'flop'), 'default') == 'default'

    store['left', 'right'] = 'update'
    assert store['left', 'right'] == 'update'

    # __getitem__ mismatched keys
    with pytest.raises(twinkeydict.TwinKeyError):
        assert store['same', 'right'] == 'no'

    # __setitem__ mismatched keys
    with pytest.raises(twinkeydict.TwinKeyError):
        store['left', 2] = 'mismatch'

    # get mismatched keys
    with pytest.raises(twinkeydict.TwinKeyError):
        store.get(('left', 2))

    # get None/None
    with pytest.raises(twinkeydict.TwinKeyError):
        assert store[None, None] == 'no'

    # set None/None
    with pytest.raises(twinkeydict.TwinKeyError):
        store[None, None] = 'pancakes'


def test_pop_del(store, items):
    for left, right, value in items:
        store[left, right] = value

    with pytest.raises(ValueError):
        del store['left']

    del store['left', None]
    assert len(store) == 2
    assert store.get(('left', 'right')) is None
    assert ('left', 'right') not in store

    assert store.pop(('same', None)) == 'twins'
    with pytest.raises(KeyError):
        store.pop(('same', 'same'))

    assert len(store) == 1
    assert (None, 'same') not in store


def test_rename(store):
    store['wabber', 'jockey'] = 'alice'
    store.rename(('wabber', None), ('blobber', None))
    with pytest.raises(twinkeydict.TwinKeyError):
        assert ('wabber', 'jockey') not in store
    assert store['blobber', 'jockey'] == 'alice'

    store.rename((None, 'jockey'), (None, 'blibber'))
    assert store['blobber', 'blibber'] == 'alice'

    store.rename(('blobber', 'blibber'), ('something', 'different'))
    assert store['something', 'different']

    with pytest.raises(twinkeydict.TwinKeyError):
        store.rename(('something', 'different'), (None, None))

    with pytest.raises(twinkeydict.TwinKeyError):
        store.rename((None, None), ('something', 'different'))

    assert store['something', 'different']
    assert len(store) == 1


def test_iterate(store, items):
    for left, right, value in items:
        store[left, right] = value

    assert len(store) == len(items)
    assert [(left, right, value) for ((left, right), value) in store.items()] == items
