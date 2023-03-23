"""
Tests brewblox_devcon_spark.datastore
"""

import asyncio

import pytest
from aiohttp import web
from aresponses import ResponsesMockServer
from brewblox_service import http, scheduler

from brewblox_devcon_spark import datastore

TESTED = datastore.__name__


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
    app['config']['isolated'] = False
    http.setup(app)
    scheduler.setup(app)
    return app


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


async def test_non_isolated(app, event_loop):
    class IsolatedTester():
        def __init__(self, isolated: bool):
            self.isolated = isolated

        @datastore.non_isolated
        async def func(self, val):
            return val

    assert await IsolatedTester(True).func('testey') is None
    assert await IsolatedTester(False).func('testey') == 'testey'
