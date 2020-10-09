"""
Tests brewblox_devcon_spark.block_store
"""


import asyncio

import pytest
from aiohttp import web
from aresponses import ResponsesMockServer
from brewblox_service import http, scheduler

from brewblox_devcon_spark import block_store, const, datastore

TESTED = block_store.__name__
DATASTORE = datastore.__name__


def read_objects():
    return block_store.SYS_OBJECTS[:1] + [
        {'keys': [f'key{i}', i+const.USER_NID_START], 'data': {}}
        for i in range(10)
    ]


def add_block_read_resp(aresponses, count, status=200):
    async def handler(request):
        return web.json_response({
            'value': {
                'id': 'XXXX',
                'namespace': block_store.NAMESPACE,
                'data': read_objects(),
            }},
            status=status)
    aresponses.add(path_pattern='/history/datastore/get',
                   method_pattern='POST',
                   response=handler,
                   repeat=count)


def add_write_resp(aresponses: ResponsesMockServer, count, status=200):
    async def handler(request):
        return web.json_response(await request.json(), status=status)
    aresponses.add(path_pattern='/history/datastore/set',
                   method_pattern='POST',
                   response=handler,
                   repeat=count)


@pytest.fixture
def app(app, mocker):
    mocker.patch(DATASTORE + '.FLUSH_DELAY_S', 0.01)
    mocker.patch(DATASTORE + '.RETRY_INTERVAL_S', 0.01)
    app['config']['volatile'] = False
    http.setup(app)
    scheduler.setup(app)
    block_store.setup(app)
    return app


@pytest.fixture
def store(app):
    return block_store.fget(app)


async def test_block_read(app, client, store, aresponses):
    assert store.active
    assert not store.volatile

    default_length = len(block_store.SYS_OBJECTS)
    read_length = default_length + len(read_objects()) - 1  # overlapping item is merged

    assert len(store.items()) == default_length

    add_block_read_resp(aresponses, 1)
    add_write_resp(aresponses, 1)
    await store.read('device-id')
    assert len(store.items()) == read_length

    # Defaults were added to read objects
    # Give them time to flush
    await asyncio.sleep(0.05)

    aresponses.assert_plan_strictly_followed()


async def test_block_write(app, client, store, aresponses):
    default_length = len(block_store.SYS_OBJECTS)
    read_length = default_length + len(read_objects()) - 1  # overlapping item is merged

    # Read and let flush
    add_block_read_resp(aresponses, 1)
    add_write_resp(aresponses, 1)
    await store.read('device-id')
    await asyncio.sleep(0.05)

    # write on add
    add_write_resp(aresponses, 1)
    store['inserted', 9001] = 'val'
    assert len(store.items()) == read_length + 1
    await asyncio.sleep(0.05)

    # write on delete
    add_write_resp(aresponses, 1)
    del store['inserted', 9001]
    assert len(store.items()) == read_length
    await asyncio.sleep(0.05)

    aresponses.assert_plan_strictly_followed()


async def test_block_read_error(app, client, store, aresponses):
    add_block_read_resp(aresponses, 1, 500)

    with pytest.warns(UserWarning, match='read error'):
        await store.read('device-id')

    assert store.key is None

    with pytest.warns(UserWarning, match='flush error'):
        await asyncio.sleep(0.05)

    # reset to normal
    add_block_read_resp(aresponses, 1)
    add_write_resp(aresponses, 1)
    await store.read('device-id')
    await asyncio.sleep(0.05)

    aresponses.assert_plan_strictly_followed()


async def test_block_write_error(app, client, store, aresponses):
    add_block_read_resp(aresponses, 1)
    add_write_resp(aresponses, 1)
    await store.read('device-id')
    await asyncio.sleep(0.05)

    # continue on write error
    add_write_resp(aresponses, 1000, status=500)
    with pytest.warns(UserWarning, match='flush error'):
        store['inserted2', 9002] = 'val'
        await asyncio.sleep(0.05)

        aresponses.assert_all_requests_matched()
        aresponses.assert_called_in_order()
        assert len(aresponses.history) > 3
        await store.shutdown(app)
