"""
Tests brewblox_devcon_spark.simple_store
"""

import asyncio
import json
from unittest.mock import mock_open

import pytest
from brewblox_service import scheduler

from brewblox_devcon_spark import simplestore

TESTED = simplestore.__name__


@pytest.fixture
def items():
    return [
        ('left', 'right', dict()),
        (1, 2, None),
        ('same', 'same', 'twins')
    ]


def as_items_json(items):
    serialized = [
        {'keys': [left, right], 'data': value}
        for (left, right, value) in items
    ]
    return json.dumps(serialized)


@pytest.fixture
def store():
    return simplestore.MultiIndexDict()


@pytest.fixture
async def app(app, loop, mocker, items):
    mocker.patch(TESTED + '.open', mock_open(read_data=as_items_json(items)))
    mocker.patch(TESTED + '.MIN_FLUSH_INTERVAL_S', 0.01)
    scheduler.setup(app)
    simplestore.setup(app)
    return app


@pytest.fixture
async def app_store(app):
    s = simplestore.get_store(app)
    assert s
    return s


@pytest.fixture
async def flusher(app):
    f = simplestore.get_flusher(app)
    assert f
    return f


def test_get_set(store, items):
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

        assert store.bothkeys((left, right)) == (left, right)
        assert store.bothkeys((left, None)) == (left, right)
        assert store.bothkeys((None, right)) == (left, right)

    assert store.get(('flip', 'flop'), 'default') == 'default'

    store['left', 'right'] = 'update'
    assert store['left', 'right'] == 'update'

    # __getitem__ mismatched keys
    with pytest.raises(simplestore.MultiIndexError):
        assert store['same', 'right'] == 'no'

    # __setitem__ mismatched keys
    with pytest.raises(simplestore.MultiIndexError):
        store['left', 2] = 'mismatch'

    # get mismatched keys
    with pytest.raises(simplestore.MultiIndexError):
        store.get(('left', 2))

    # get None/None
    with pytest.raises(simplestore.MultiIndexError):
        assert store[None, None] == 'no'

    # set None/None
    with pytest.raises(simplestore.MultiIndexError):
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


def test_iterate(store, items):
    for left, right, value in items:
        store[left, right] = value

    assert len(store) == len(items)
    assert [(left, right, value) for ((left, right), value) in store.items()] == items


def test_load(app, app_store, mocker, items):
    assert len(app_store) == len(items)
    left, right, value = items[0]
    assert app_store[left, right] == value


async def test_flush_lifecycle(app, client, store, test_db):
    floosh = simplestore.Flusher(app, store, test_db)
    assert not floosh.active
    await floosh.startup(app)
    assert floosh.active
    await floosh.shutdown(app)
    assert not floosh.active
    await floosh.shutdown(app)
    await floosh.startup(app)
    await floosh.shutdown(app)


async def test_flush_noload(app, client, store, mocker):
    open_mock = mocker.patch(TESTED + '.open')
    open_mock.side_effect = FileNotFoundError
    set_spy = mocker.spy(store, '__setitem__')

    simplestore.Flusher(app, store, 'filey')
    assert open_mock.call_count == 1
    assert set_spy.call_count == 0


async def test_flush(app, client, app_store, flusher, items, mocker):
    save_spy = mocker.spy(flusher, '_save_objects')

    left, right, value = 'Huey', 'Dewey', 'Louie'
    app_store[left, right] = value
    assert app_store[left, right]
    items.append((left, right, value))

    await asyncio.sleep(0.1)
    assert save_spy.call_count > 0


async def test_flush_error(app, client, app_store, flusher, mocker):
    save_mock = mocker.patch.object(flusher, '_save_objects')
    save_mock.side_effect = RuntimeError

    left, right, value = 'Huey', 'Dewey', 'Louie'
    app_store[left, right] = value

    await asyncio.sleep(0.1)
    assert save_mock.call_count > 0
    assert flusher.active
