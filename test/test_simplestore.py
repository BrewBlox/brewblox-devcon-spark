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
    mocker.patch(TESTED + '.FLUSH_DELAY_S', 0.01)
    scheduler.setup(app)
    simplestore.setup(app)
    return app


@pytest.fixture
async def file_store(app):
    return simplestore.get_object_store(app)


@pytest.fixture
async def readonly_store(app):
    return simplestore.get_system_store(app)


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


def test_rename(store):
    store['wabber', 'jockey'] = 'alice'
    store.rename(('wabber', None), ('blobber', None))
    assert ('wabber', 'jockey') not in store
    assert store['blobber', 'jockey'] == 'alice'

    store.rename((None, 'jockey'), (None, 'blibber'))
    assert store['blobber', 'blibber'] == 'alice'

    store.rename(('blobber', 'blibber'), ('something', 'different'))
    assert store['something', 'different']

    with pytest.raises(simplestore.MultiIndexError):
        store.rename(('something', 'different'), (None, None))

    with pytest.raises(simplestore.MultiIndexError):
        store.rename((None, None), ('something', 'different'))

    assert store['something', 'different']
    assert len(store) == 1


def test_iterate(store, items):
    for left, right, value in items:
        store[left, right] = value

    assert len(store) == len(items)
    assert [(left, right, value) for ((left, right), value) in store.items()] == items


def test_read_file(app, file_store, mocker, items):
    assert len(file_store) == len(items)
    left, right, value = items[0]
    assert file_store[left, right] == value


async def test_flush_lifecycle(app, client, store, test_db, mocker):
    floosh = simplestore.MultiIndexFileDict(app, test_db)
    save_spy = mocker.spy(floosh, 'write_file')

    assert not floosh.active
    await floosh.startup(app)
    assert floosh.active
    await floosh.shutdown(app)
    assert not floosh.active
    await floosh.shutdown(app)
    await floosh.startup(app)
    await floosh.shutdown(app)

    # Can insert/delete when not running, but will not save
    del floosh[next(k for k in floosh)]
    floosh['tic', 'tac'] = 'toe'
    assert save_spy.call_count == 0


async def test_no_file(app, client, mocker):
    open_mock = mocker.patch(TESTED + '.open')
    open_mock.side_effect = FileNotFoundError

    storey = simplestore.MultiIndexFileDict(app, 'filey')
    assert open_mock.call_count == 1
    assert len(storey) == 0


async def test_load_error(app, client, mocker):
    open_mock = mocker.patch(TESTED + '.open')
    open_mock.side_effect = RuntimeError

    with pytest.raises(RuntimeError):
        simplestore.MultiIndexFileDict(app, 'filey')
    assert open_mock.call_count == 1


async def test_write(app, client, file_store, items, mocker):
    save_spy = mocker.spy(file_store, 'write_file')

    left, right, value = 'Huey', 'Dewey', 'Louie'
    file_store[left, right] = value
    assert file_store[left, right]
    items.append((left, right, value))

    await asyncio.sleep(0.1)
    assert save_spy.call_count == 1

    save_spy.reset_mock()
    await asyncio.sleep(0.1)
    assert save_spy.call_count == 0

    del file_store[left, right]
    await asyncio.sleep(0.1)
    assert save_spy.call_count == 1


async def test_write_error(app, client, file_store, mocker):
    save_mock = mocker.patch.object(file_store, 'write_file')
    save_mock.side_effect = RuntimeError

    file_store['leftey', 'rightey'] = 'floppy'

    await asyncio.sleep(0.1)
    assert save_mock.call_count > 0
    assert file_store.active


async def test_readonly(app, client, readonly_store):
    assert len(readonly_store)

    with pytest.raises(TypeError):
        await readonly_store.write_file()

    with pytest.raises(TypeError):
        del readonly_store['onewirebus', None]

    with pytest.raises(TypeError):
        readonly_store['-', '-'] = '=)'
