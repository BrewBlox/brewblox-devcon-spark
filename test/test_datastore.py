"""
Tests datastore.py
"""

import asyncio
import os

import pytest
from brewblox_devcon_spark import datastore
from brewblox_service import scheduler

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
def file_store(app, database_test_file):
    scheduler.setup(app)
    return datastore.FileDataStore(
        app=app,
        filename=database_test_file,
        read_only=False,
    )


@pytest.fixture
def memory_store(app):
    return datastore.MemoryDataStore(app)


@pytest.fixture
def stores(file_store, memory_store, client):
    return [file_store, memory_store]


@pytest.fixture
def obj():
    return {
        'service_id': 'pancakes',
        'type': 6,
        'obj': {
            'settings': {
                'address': 'KP7p/ggAABc=',
                'offset': 0
            }
        }
    }


async def test_basics(stores, app):
    for store in stores:
        assert str(store)

        await store.shutdown()
        await store.shutdown()

        await store.startup(app)
        await store.shutdown()


async def test_insert(stores, obj):
    for store in stores:
        await store.insert(obj)
        assert await store.find('service_id', obj['service_id']) == [obj]


async def test_insert_multiple(stores, obj):
    for store in stores:
        await store.insert_multiple([obj]*100)
        assert len(await store.find('service_id', obj['service_id'])) == 100


async def test_insert_unique(stores, obj):
    for store in stores:
        await store.insert_unique('service_id', obj)

        # already exists
        with pytest.raises(datastore.NotUniqueError):
            await store.insert_unique('service_id', obj)

        # obj[pancakes] does not exist
        with pytest.raises(KeyError):
            await store.insert_unique('pancakes', obj)

        assert await store.find('service_id', obj['service_id']) == [obj]

        # Add another obj to create a conflict
        await store.insert(obj)

        with pytest.raises(datastore.ConflictDetectedError):
            await store.insert_unique('service_id', obj)


async def test_update(stores):
    for store in stores:
        await store.insert_multiple([{'id': i} for i in range(10)])
        await store.update('id', 6, {'something': 'different'})

        obj = await store.find('id', 6)
        assert obj[0]['something'] == 'different'

        await store.update('id', 6, {'id': 101})
        assert not await store.find('id', 6)


async def test_update_unique(stores, obj):
    for store in stores:
        await store.insert_multiple([obj]*10)
        await store.insert_multiple([{'service_id': i} for i in range(10)])

        await store.update_unique('service_id', 8, {'something': 'different'})

        with pytest.raises(datastore.ConflictDetectedError):
            await store.update_unique('service_id', obj['service_id'], obj)


async def test_delete(stores, obj):
    for store in stores:
        await store.insert_multiple([obj]*10)
        await store.delete('service_id', obj['service_id'])

        await store.insert_unique('service_id', obj)
        await store.insert_unique('service_id', {'service_id': 'waffles'})

        await store.delete('service_id', 'steve')
        await store.delete('service_id', 'waffles')

        assert await store.find('service_id', obj['service_id'])
        assert not await store.find('service_id', 'steve')


async def test_purge(stores, obj):
    for store in stores:
        await store.insert_multiple([obj]*10)
        await store.purge()
        assert len(await store.all()) == 0


async def test_spam(stores, obj):
    """
    Tests coherence of database write actions when running many non-sequential async tasks
    """
    for store in stores:
        data = [dict(obj) for i in range(100)]
        await asyncio.wait([asyncio.ensure_future(store.insert(d)) for d in data])

        result = await store.all()
        assert len(data) == len(result)


async def test_exception_handling(stores, mocker):
    for store in stores:
        with pytest.raises(ArithmeticError):
            await store._do_with_db(lambda db: 1 / 0)


async def test_find_unique(stores, obj):
    for store in stores:
        await store.insert_multiple([obj]*2)

        with pytest.raises(datastore.ConflictDetectedError):
            await store.find_unique('service_id', obj['service_id'])


async def test_known_conflicts(stores, obj):
    for store in stores:
        await store.insert_multiple([obj]*2)
        await store.insert_unique('service_id', {'service_id': 'waffles'})

        # Nobody noticed the conflicts yet
        assert not await store.known_conflicts()

        with pytest.raises(datastore.ConflictDetectedError):
            await store.find_unique('service_id', obj['service_id'])

        assert await store.known_conflicts() == {
            'service_id': {
                obj['service_id']: [obj]*2
            }
        }
