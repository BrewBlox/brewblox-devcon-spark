"""
Tests brewblox_devcon_spark.datastore_blocks
"""


import asyncio
from datetime import timedelta
from unittest.mock import ANY

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from pytest_httpx import HTTPXMock

from brewblox_devcon_spark import const, datastore_blocks, utils
from brewblox_devcon_spark.models import TwinKeyEntry

TESTED = datastore_blocks.__name__


def read_objects() -> list[TwinKeyEntry]:
    return datastore_blocks.SYS_OBJECTS[:1] + [
        TwinKeyEntry(keys=(f'key{i}', i+const.USER_NID_START), data={})
        for i in range(10)
    ]


@pytest.fixture
def app() -> FastAPI:
    config = utils.get_config()
    config.datastore_flush_delay = timedelta()

    datastore_blocks.setup()
    return FastAPI()


@pytest.fixture(autouse=True)
async def manager(manager: LifespanManager):
    yield manager


async def test_load_save(httpx_mock: HTTPXMock):
    config = utils.get_config()
    store = datastore_blocks.CV.get()

    default_length = len(datastore_blocks.SYS_OBJECTS)
    read_length = default_length + len(read_objects()) - 1  # overlapping item is merged

    assert len(store.items()) == default_length

    # Can't save before loading
    with pytest.raises(ValueError):
        await store.save()

    # Shutdown does nothing, but also doesn't complain
    await store.on_shutdown()

    # Invalid format
    httpx_mock.add_response(url=f'{config.datastore_url}/get',
                            match_json={'id': '5678-blocks-db',
                                        'namespace': const.SERVICE_NAMESPACE},
                            json={})

    httpx_mock.add_response(url=f'{config.datastore_url}/get',
                            match_json={'id': '5678-blocks-db',
                                        'namespace': const.SERVICE_NAMESPACE},
                            json={
                                'value': {
                                    'id': '5678-blocks-db',
                                    'namespace': const.SERVICE_NAMESPACE,
                                    'data': [v.model_dump(mode='json')
                                             for v in read_objects()],
                                },
                            })

    httpx_mock.add_response(url=f'{config.datastore_url}/set',
                            match_json={
                                'value': {
                                    'id': '5678-blocks-db',
                                    'namespace': const.SERVICE_NAMESPACE,
                                    'data': ANY
                                },
                            })

    # First attempt gets invalid data, and falls back on defaults
    await store.load('5678')
    assert len(store.items()) == default_length

    await store.load('5678')
    assert len(store.items()) == read_length

    async with utils.task_context(store.repeat()):
        # Flush on insert
        store['inserted', 9001] = {}
        assert len(store.items()) == read_length + 1
        await asyncio.sleep(0)

        # Flush on remove
        del store['inserted', 9001]
        assert len(store.items()) == read_length
        await asyncio.sleep(0)

        # Does nothing if not changed
        await store.on_shutdown()

    assert len(httpx_mock.get_requests(url=f'{config.datastore_url}/set')) < 3


async def test_load_error(httpx_mock: HTTPXMock):
    config = utils.get_config()
    store = datastore_blocks.CV.get()

    httpx_mock.add_response(url=f'{config.datastore_url}/get',
                            match_json={'id': '5678-blocks-db',
                                        'namespace': const.SERVICE_NAMESPACE},
                            json={
                                'value': {
                                    'id': '5678-blocks-db',
                                    'namespace': const.SERVICE_NAMESPACE,
                                    'data': 'miniaturized giant hamsters from outer space',
                                },
                            })

    # Removed after load
    store['inserted', 9001] = {}

    await store.load('5678')
    assert len(store.items()) == len(datastore_blocks.SYS_OBJECTS)
