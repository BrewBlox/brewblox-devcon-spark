"""
Tests brewblox_devcon_spark.datastore.settings_store
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, Request, Response
from pytest_httpx import HTTPXMock
from pytest_mock import MockerFixture

from brewblox_devcon_spark import const, mqtt, utils
from brewblox_devcon_spark.datastore import settings_store
from brewblox_devcon_spark.models import DatastoreSingleValueBox

TESTED = settings_store.__name__


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mqtt.lifespan():
        yield


@pytest.fixture(autouse=True)
def app(mocker: MockerFixture) -> FastAPI:
    mocker.patch(TESTED + '.FETCH_TIMEOUT', timedelta(seconds=1))

    mqtt.setup()
    settings_store.setup()
    return FastAPI(lifespan=lifespan)


async def test_fetch_all(httpx_mock: HTTPXMock):
    store = settings_store.CV.get()
    config = utils.get_config()

    httpx_mock.add_response(url=f'{config.datastore_url}/get',
                            match_json={'id': config.name,
                                        'namespace': const.SERVICE_NAMESPACE},
                            json={
                                'value': {
                                    'id': config.name,
                                    'namespace': const.SERVICE_NAMESPACE,
                                    'enabled': False,
                                },
                            })

    httpx_mock.add_response(url=f'{config.datastore_url}/get',
                            match_json={'id': const.GLOBAL_UNITS_ID,
                                        'namespace': const.GLOBAL_NAMESPACE},
                            json={
                                'value': {
                                    'id': const.GLOBAL_UNITS_ID,
                                    'namespace': const.GLOBAL_NAMESPACE,
                                    'temperature': 'degF',
                                },
                            })

    httpx_mock.add_response(url=f'{config.datastore_url}/get',
                            match_json={'id': const.GLOBAL_TIME_ZONE_ID,
                                        'namespace': const.GLOBAL_NAMESPACE},
                            json={
                                'value': {
                                    'id': const.GLOBAL_TIME_ZONE_ID,
                                    'namespace': const.GLOBAL_NAMESPACE,
                                    'name': 'Europe/Amsterdam',
                                    'posixValue': 'CET-1CEST,M3.5.0,M10.5.0/3',
                                },
                            })

    await store.fetch_all()
    assert store.service_settings.enabled is False
    assert store.unit_settings.temperature == 'degF'
    assert store.timezone_settings.name == 'Europe/Amsterdam'


async def test_commit(httpx_mock: HTTPXMock):
    config = utils.get_config()
    store = settings_store.CV.get()
    request_received = False

    async def request_callback(request: Request) -> Response:
        assert request.url == f'{config.datastore_url}/set'
        box = DatastoreSingleValueBox.model_validate_json(request.read())
        raw_value = box.value.model_dump()
        assert raw_value['enabled'] is False

        nonlocal request_received
        request_received = True

        return Response(status_code=200, json=box.model_dump(mode='json'))

    httpx_mock.add_callback(request_callback)

    store.service_settings.enabled = False
    await store.commit_service_settings()
    assert request_received


async def test_store_events(client: AsyncClient):
    config = utils.get_config()
    mqtt_client = mqtt.CV.get()
    store = settings_store.CV.get()
    service_evt_received = asyncio.Event()
    global_evt_received = asyncio.Event()

    async def service_evt_callback():
        assert store.service_settings.enabled is False
        service_evt_received.set()

    async def global_evt_callback():
        assert store.unit_settings.temperature == 'degF'
        assert store.timezone_settings.name == 'Europe/Amsterdam'
        global_evt_received.set()

    store.service_settings_listeners.add(service_evt_callback)
    store.global_settings_listeners.add(global_evt_callback)

    mqtt_client.publish('brewcast/datastore/brewblox-global',
                        {
                            'changed': [
                                {
                                    'id': const.GLOBAL_UNITS_ID,
                                    'namespace': const.GLOBAL_NAMESPACE,
                                    'temperature': 'degF',
                                },
                                {
                                    'id': const.GLOBAL_TIME_ZONE_ID,
                                    'namespace': const.GLOBAL_NAMESPACE,
                                    'name': 'Europe/Amsterdam',
                                    'posixValue': 'CET-1CEST,M3.5.0,M10.5.0/3',
                                }
                            ]
                        })

    mqtt_client.publish('brewcast/datastore/brewblox-devcon-spark',
                        {
                            'changed': [
                                {
                                    'id': config.name,
                                    'namespace': const.SERVICE_NAMESPACE,
                                    'enabled': False,
                                },
                                {
                                    'id': 'spark-other',
                                    'namespace': const.SERVICE_NAMESPACE,
                                    'enabled': True,
                                }
                            ]
                        })

    async with asyncio.timeout(10):
        await service_evt_received.wait()
        await global_evt_received.wait()
