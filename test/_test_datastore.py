"""
Tests brewblox_devcon_spark.datastore
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta

import pytest
from fastapi import FastAPI
from pytest_httpx import HTTPXMock
from pytest_mock import MockerFixture

from brewblox_devcon_spark import datastore
from brewblox_devcon_spark.models import ServiceConfig

TESTED = datastore.__name__


def add_check_resp(aresponses: ResponsesMockServer, count, status=200):
    async def handler(request):
        return web.json_response({'ping': 'pong'}, status=status)
    aresponses.add(path_pattern='/history/datastore/ping',
                   method_pattern='GET',
                   response=handler,
                   repeat=count)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


@pytest.fixture
def app(mocker: MockerFixture) -> FastAPI:
    mocker.patch(TESTED + '.FLUSH_DELAY', timedelta(milliseconds=1))
    mocker.patch(TESTED + '.RETRY_INTERVAL', timedelta(milliseconds=1))


@pytest.fixture
def setup(app, mocker):
    mocker.patch(TESTED + '.FLUSH_DELAY_S', 0.01)
    mocker.patch(TESTED + '.RETRY_INTERVAL_S', 0.01)

    config = utils.get_config()
    config.isolated = False

    http.setup(app)
    scheduler.setup(app)


async def test_wait_datastore_ready(app, client, aresponses: ResponsesMockServer):
    add_check_resp(aresponses, 10, 405)
    add_check_resp(aresponses, 1)
    await asyncio.wait_for(datastore.wait_datastore_ready(app), timeout=1)
    aresponses.assert_all_requests_matched()


async def test_cancel_wait_datastore_ready(app, client, aresponses: ResponsesMockServer):
    add_check_resp(aresponses, 100, 405)
    # The function should respond to the CancelledError raised by wait_for() timeout
    # Sadly, if this test fails, it will completely block test execution
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(datastore.wait_datastore_ready(app), timeout=0.001)


async def test_non_isolated(app, event_loop):
    class IsolatedTester():
        def __init__(self, isolated: bool):
            self.isolated = isolated

        @datastore.non_isolated
        async def func(self, val):
            return val

    assert await IsolatedTester(True).func('testey') is None
    assert await IsolatedTester(False).func('testey') == 'testey'
