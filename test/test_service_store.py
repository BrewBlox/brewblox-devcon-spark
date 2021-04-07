"""
Tests brewblox_devcon_spark.service_store
"""


import asyncio

import pytest
from aiohttp import web
from aresponses import ResponsesMockServer
from brewblox_service import http, scheduler

from brewblox_devcon_spark import const, datastore, service_store

TESTED = service_store.__name__
DATASTORE = datastore.__name__


def add_config_read_resp(aresponses, count, status=200):
    async def handler(request):
        return web.json_response({
            'value': {
                'id': 'XXXX',
                'namespace': const.SPARK_NAMESPACE,
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


@pytest.fixture
def app(app, mocker):
    mocker.patch(DATASTORE + '.FLUSH_DELAY_S', 0.01)
    mocker.patch(DATASTORE + '.RETRY_INTERVAL_S', 0.01)
    app['config']['volatile'] = False
    http.setup(app)
    scheduler.setup(app)
    service_store.setup(app)
    return app


@pytest.fixture
def store(app):
    return service_store.fget(app)


async def test_config_read(app, client, store, aresponses):
    assert store.active
    assert not store.volatile

    add_config_read_resp(aresponses, 1)
    await store.read()
    await asyncio.sleep(0.05)

    aresponses.assert_plan_strictly_followed()


async def test_config_read_error(app, client, store, aresponses):
    assert store.active
    assert not store.volatile

    add_config_read_resp(aresponses, 1, 405)
    with pytest.warns(UserWarning, match='read error'):
        await store.read()
        await asyncio.sleep(0.05)

    with store.open() as cfg:
        assert cfg == {}

    aresponses.assert_plan_strictly_followed()


async def test_config_read_empty(app, client, store, aresponses):
    assert store.active
    assert not store.volatile

    aresponses.add(path_pattern='/history/datastore/get',
                   method_pattern='POST',
                   response={'value': None})
    with pytest.warns(UserWarning, match='found no config'):
        await store.read()
        await asyncio.sleep(0.05)

    with store.open() as cfg:
        assert cfg == {}

    aresponses.assert_plan_strictly_followed()


async def test_config_write(app, client, store, aresponses):

    add_config_read_resp(aresponses, 1)
    add_write_resp(aresponses, 1)
    await store.read()

    # Dummy - should not trigger write
    with store.open() as cfg:
        pass
    await asyncio.sleep(0.05)

    # Actual write
    with store.open() as cfg:
        cfg['newkey'] = True
    await asyncio.sleep(0.05)

    aresponses.assert_plan_strictly_followed()
