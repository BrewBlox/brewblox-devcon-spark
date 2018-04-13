"""
Tests datastore.py
"""

import asyncio
import os
from pathlib import Path

import pytest
from brewblox_devcon_spark import datastore

TESTED = datastore.__name__


@pytest.fixture
def database_test_file():
    def remove(f):
        try:
            os.remove(f)
        except FileNotFoundError:
            pass

    f = 'test_file.json'
    remove(f)
    yield f
    remove(f)


@pytest.fixture
async def file_store(app, client, database_test_file, loop):
    store = datastore.FileDataStore(
        filename=database_test_file,
        read_only=False,
        primary_key='pk'
    )
    await store.start(loop=loop)
    await store.purge()
    yield store
    await store.close()


@pytest.fixture
async def memory_store(app, client, loop):
    store = datastore.MemoryDataStore(primary_key='pk')
    await store.start(loop=loop)
    yield store
    await store.close()


@pytest.fixture
async def stores(file_store, memory_store):
    return [file_store, memory_store]


@pytest.fixture
def obj():
    return {
        'pk': 'pancakes',
        'type': 6,
        'obj': {
            'settings': {
                'address': 'KP7p/ggAABc=',
                'offset': 0
            }
        }
    }


async def test_basics(client, stores, loop):
    for store in stores:
        assert str(store)

        await store.close()
        await store.close()

        await store.start(loop)
        await store.close()


async def test_file_start_stop(client, database_test_file, loop):
    store = datastore.FileDataStore(filename=database_test_file, read_only=False)
    assert not Path(database_test_file).exists()

    await store.close()
    await store.close()

    await store.start(loop)
    await asyncio.sleep(0.001)
    assert Path(database_test_file).exists()

    await store.close()
    assert Path(database_test_file).exists()


async def test_write(stores, obj):
    for store in stores:
        await store.write(obj)
        assert await store.find_by_id(obj[store.primary_key]) == obj


async def test_spam(stores, mocker, obj):
    """
    Tests coherence of database write actions when running many non-sequential async tasks
    """
    for store in stores:
        write_spy = mocker.spy(store, 'write')

        data = [dict(obj) for i in range(100)]
        await asyncio.wait([asyncio.ensure_future(store.write(d)) for d in data])

        result = await store.all()
        assert write_spy.call_count == len(data)
        assert len(data) == len(result)


async def test_exception_handling(stores, mocker):
    for store in stores:
        with pytest.raises(ArithmeticError):
            await store._do_with_db(lambda db: 1 / 0)


async def test_update_by_id(stores, obj):
    for store in stores:
        id = obj[store.primary_key]
        await store.create_by_id(id, obj)

        obj['type'] = 42
        await store.update_by_id(id, obj)

        read = await store.find_by_id(id)
        assert read['type'] == 42
