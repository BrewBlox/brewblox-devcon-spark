"""
Tests brewblox_devcon_spark.simple_store
"""

import asyncio
import json
from unittest.mock import mock_open

import pytest
from brewblox_service import features, scheduler

from brewblox_devcon_spark import twinkeydict

TESTED = twinkeydict.__name__


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
    return twinkeydict.TwinKeyDict()


@pytest.fixture
async def app(app, loop, mocker, items, test_db):
    mocker.patch(TESTED + '.open', mock_open(read_data=as_items_json(items)))
    mocker.patch(TESTED + '.FLUSH_DELAY_S', 0.01)
    scheduler.setup(app)

    features.add(app,
                 twinkeydict.TwinKeyFileDict(app, test_db),
                 key='store')
    features.add(app,
                 twinkeydict.TwinKeyFileDict(app, test_db, read_only=True),
                 key='readonly_store')

    return app


@pytest.fixture
async def file_store(app):
    return features.get(app, key='store')


@pytest.fixture
async def readonly_store(app):
    return features.get(app, key='readonly_store')


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


def test_read_file(app, file_store, mocker, items):
    assert len(file_store) == len(items)
    left, right, value = items[0]
    assert file_store[left, right] == value


async def test_flush_lifecycle(app, client, store, test_db, mocker):
    floosh = twinkeydict.TwinKeyFileDict(app, test_db)
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

    storey = twinkeydict.TwinKeyFileDict(app, 'filey')
    assert open_mock.call_count == 1
    assert len(storey) == 0


async def test_load_error(app, client, mocker):
    open_mock = mocker.patch(TESTED + '.open')
    open_mock.side_effect = RuntimeError

    with pytest.raises(RuntimeError):
        twinkeydict.TwinKeyFileDict(app, 'filey')
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
