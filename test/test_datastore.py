"""
Tests datastore.py
"""

import asyncio
import os
from pathlib import Path
from unittest.mock import Mock

import pytest
from brewblox_devcon_spark import datastore


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
async def store(app, client, database_test_file, loop):
    store = datastore.DataStore(file=database_test_file)
    await store.start(loop=loop)
    await store.purge()
    return store


@pytest.fixture
def obj():
    return {
        'type': 6,
        'alias': 'pancakes',
        'obj': {
            'settings': {
                'address': 'KP7p/ggAABc=',
                'offset': 0
            }
        }
    }


async def test_start_stop(client, database_test_file, loop):
    store = datastore.DataStore(file=database_test_file)
    assert not Path(database_test_file).exists()

    await store.close()
    await store.close()

    await store.start(loop)
    await asyncio.sleep(0.001)
    assert Path(database_test_file).exists()

    await store.close()
    assert Path(database_test_file).exists()


async def test_write(store, obj):
    await store.write(obj)
    assert await store.find_by_id(obj['alias']) == obj


async def test_spam(store, mocker, obj):
    """
    Tests coherence of database write actions when running many non-sequential async tasks
    """
    write_spy = mocker.spy(store, 'write')

    data = [dict(obj) for i in range(100)]
    await asyncio.wait([asyncio.ensure_future(store.write(d)) for d in data])

    result = await store.all()
    assert write_spy.call_count == len(data)
    assert len(data) == len(result)


async def test_exception_handling(store, mocker):
    with pytest.raises(ArithmeticError):
        await store._do_with_db(lambda db: 1 / 0)

    log_spy = mocker.spy(datastore.LOGGER, 'warn')

    err_action = Mock()
    err_action.do.side_effect = RecursionError

    await store._pending_actions.put(err_action)
    await asyncio.sleep(0.01)

    assert log_spy.call_count == 1
