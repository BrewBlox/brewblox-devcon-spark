"""
Tests brewblox_devcon_spark.datastore
"""

import asyncio

import pytest
from aiohttp import web
from aresponses import ResponsesMockServer
from brewblox_service import http, scheduler

from brewblox_devcon_spark import const, datastore

TESTED = datastore.__name__


def read_objects():
    return datastore.SYS_OBJECTS[:1] + [
        {'keys': [f'key{i}', i+const.USER_NID_START], 'data': {}}
        for i in range(10)
    ]


def add_block_read_resp(aresponses, count, status=200):
    async def handler(request):
        return web.json_response({
            'value': {
                'id': 'XXXX',
                'namespace': datastore.NAMESPACE,
                'data': read_objects(),
            }},
            status=status)
    aresponses.add(path_pattern='/history/datastore/get',
                   method_pattern='POST',
                   response=handler,
                   repeat=count)


def add_config_read_resp(aresponses, count, status=200):
    async def handler(request):
        return web.json_response({
            'value': {
                'id': 'XXXX',
                'namespace': datastore.NAMESPACE,
                'data': {'k1': 'v1', 'k2': 'v2'},
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


def add_check_resp(aresponses: ResponsesMockServer, count, status=200):
    async def handler(request):
        return web.json_response({'ping': 'pong'}, status=status)
    aresponses.add(path_pattern='/history/datastore/ping',
                   method_pattern='GET',
                   response=handler,
                   repeat=count)


@pytest.fixture
def app(app, mocker):
    mocker.patch(TESTED + '.FLUSH_DELAY_S', 0.01)
    mocker.patch(TESTED + '.RETRY_INTERVAL_S', 0.01)
    app['config']['volatile'] = False
    http.setup(app)
    scheduler.setup(app)
    datastore.setup(app)
    return app


@pytest.fixture
def block_store(app):
    return datastore.get_block_store(app)


@pytest.fixture
def config_store(app):
    return datastore.get_config_store(app)


async def test_check_remote(app, client, aresponses: ResponsesMockServer):
    add_check_resp(aresponses, 10, 405)
    add_check_resp(aresponses, 1)
    await asyncio.wait_for(datastore.check_remote(app), timeout=1)
    aresponses.assert_all_requests_matched()


async def test_cancel_check_remote(app, client, aresponses: ResponsesMockServer):
    add_check_resp(aresponses, 100, 405)
    # The function should respond to the CancelledError raised by wait_for() timeout
    # Sadly, if this test fails, it will completely block test execution
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(datastore.check_remote(app), timeout=0.001)


async def test_non_volatile(app, loop):
    class VolatileTester():
        def __init__(self, volatile: bool):
            self.volatile = volatile

        @datastore.non_volatile
        async def func(self, val):
            return val

    assert await VolatileTester(True).func('testey') is None
    assert await VolatileTester(False).func('testey') == 'testey'


async def test_block_read(app, client, block_store, aresponses):
    assert block_store.active
    assert not block_store.volatile

    default_length = len(datastore.SYS_OBJECTS)
    read_length = default_length + len(read_objects()) - 1  # overlapping item is merged

    assert len(block_store.items()) == default_length

    add_block_read_resp(aresponses, 1)
    add_write_resp(aresponses, 1)
    await block_store.read('device-id')
    assert len(block_store.items()) == read_length

    # Defaults were added to read objects
    # Give them time to flush
    await asyncio.sleep(0.05)

    aresponses.assert_plan_strictly_followed()


async def test_block_write(app, client, block_store, aresponses):
    default_length = len(datastore.SYS_OBJECTS)
    read_length = default_length + len(read_objects()) - 1  # overlapping item is merged

    # Read and let flush
    add_block_read_resp(aresponses, 1)
    add_write_resp(aresponses, 1)
    await block_store.read('device-id')
    await asyncio.sleep(0.05)

    # write on add
    add_write_resp(aresponses, 1)
    block_store['inserted', 9001] = 'val'
    assert len(block_store.items()) == read_length + 1
    await asyncio.sleep(0.05)

    # write on delete
    add_write_resp(aresponses, 1)
    del block_store['inserted', 9001]
    assert len(block_store.items()) == read_length
    await asyncio.sleep(0.05)

    aresponses.assert_plan_strictly_followed()


async def test_block_read_error(app, client, block_store, aresponses):
    add_block_read_resp(aresponses, 1, 500)

    with pytest.warns(UserWarning, match='read error'):
        await block_store.read('device-id')

    assert block_store.key is None

    with pytest.warns(UserWarning, match='flush error'):
        await asyncio.sleep(0.05)

    # reset to normal
    add_block_read_resp(aresponses, 1)
    add_write_resp(aresponses, 1)
    await block_store.read('device-id')
    await asyncio.sleep(0.05)

    aresponses.assert_plan_strictly_followed()


async def test_block_write_error(app, client, block_store, aresponses):
    add_block_read_resp(aresponses, 1)
    add_write_resp(aresponses, 1)
    await block_store.read('device-id')
    await asyncio.sleep(0.05)

    # continue on write error
    add_write_resp(aresponses, 1000, status=500)
    with pytest.warns(UserWarning, match='flush error'):
        block_store['inserted2', 9002] = 'val'
        await asyncio.sleep(0.05)

        aresponses.assert_all_requests_matched()
        aresponses.assert_called_in_order()
        assert len(aresponses.history) > 3


async def test_config_read(app, client, config_store, aresponses):
    assert config_store.active
    assert not config_store.volatile

    add_config_read_resp(aresponses, 1)
    await config_store.read()
    await asyncio.sleep(0.05)

    aresponses.assert_plan_strictly_followed()


async def test_config_read_error(app, client, config_store, aresponses):
    assert config_store.active
    assert not config_store.volatile

    add_config_read_resp(aresponses, 1, 405)
    with pytest.warns(UserWarning, match='read error'):
        await config_store.read()
        await asyncio.sleep(0.05)

    with config_store.open() as cfg:
        assert cfg == {}

    aresponses.assert_plan_strictly_followed()


async def test_config_read_empty(app, client, config_store, aresponses):
    assert config_store.active
    assert not config_store.volatile

    aresponses.add(path_pattern='/history/datastore/get',
                   method_pattern='POST',
                   response={'value': None})
    with pytest.warns(UserWarning, match='found no config'):
        await config_store.read()
        await asyncio.sleep(0.05)

    with config_store.open() as cfg:
        assert cfg == {}

    aresponses.assert_plan_strictly_followed()


async def test_config_write(app, client, config_store, aresponses):

    add_config_read_resp(aresponses, 1)
    add_write_resp(aresponses, 1)
    await config_store.read()

    # Dummy - should not trigger write
    with config_store.open() as cfg:
        pass
    await asyncio.sleep(0.05)

    # Actual write
    with config_store.open() as cfg:
        cfg['newkey'] = True
    await asyncio.sleep(0.05)

    aresponses.assert_plan_strictly_followed()
