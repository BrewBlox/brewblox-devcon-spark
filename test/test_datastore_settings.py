"""
Tests brewblox_devcon_spark.datastore_settings
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import Request, Response
from pytest_httpx import HTTPXMock
from pytest_mock import MockerFixture

from brewblox_devcon_spark import const, datastore_settings, mqtt, utils
from brewblox_devcon_spark.models import DatastoreSingleValueBox

TESTED = datastore_settings.__name__


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mqtt.lifespan():
        yield


@pytest.fixture(autouse=True)
def app(mocker: MockerFixture) -> FastAPI:
    config = utils.get_config()
    config.datastore_fetch_timeout = timedelta(seconds=1)

    mqtt.setup()
    datastore_settings.setup()
    return FastAPI(lifespan=lifespan)


async def test_fetch_all(httpx_mock: HTTPXMock):
    store = datastore_settings.CV.get()
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
    store = datastore_settings.CV.get()
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


async def test_store_events(manager: LifespanManager):
    config = utils.get_config()
    mqtt_client = mqtt.CV.get()
    store = datastore_settings.CV.get()

    service_evt_received = asyncio.Event()
    global_evt_received = asyncio.Event()

    num_service_events = 0
    num_global_events = 0

    async def service_evt_callback():
        assert store.service_settings.enabled is False
        nonlocal num_service_events
        num_service_events += 1
        service_evt_received.set()

    async def global_evt_callback():
        assert store.unit_settings.temperature == 'degF'
        assert store.timezone_settings.name == 'Europe/Amsterdam'
        nonlocal num_global_events
        num_global_events += 1
        global_evt_received.set()

    store.service_settings_listeners.add(service_evt_callback)
    store.global_settings_listeners.add(global_evt_callback)

    for _ in range(5):
        mqtt_client.publish(f'brewcast/datastore/{const.GLOBAL_NAMESPACE}',
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

    for _ in range(5):
        mqtt_client.publish(f'brewcast/datastore/{const.SERVICE_NAMESPACE}',
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

    assert num_global_events == 1
    assert num_service_events == 1
