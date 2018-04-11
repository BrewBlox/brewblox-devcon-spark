"""
Tests datastore.py
"""

import asyncio

import pytest
from brewblox_devcon_spark import datastore


@pytest.fixture
async def app(app):
    """App with relevant setup functions called"""
    datastore.setup(app)
    return app


@pytest.fixture
async def store(app, client):
    store = datastore.get_datastore(app)
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


async def test_write(store, obj):
    await store.write(obj)
    assert await store.find(obj['alias']) == [obj]


async def test_spam(store, mocker, obj):
    """
    Tests coherence of database write actions when running many non-sequential async tasks
    """
    write_spy = mocker.spy(store, 'write')

    data = [dict(obj) for i in range(100)]
    await asyncio.wait([asyncio.ensure_future(store.write(d)) for d in data])

    result = await store.find('pancakes')
    assert write_spy.call_count == len(data)
    assert len(data) == len(result)
