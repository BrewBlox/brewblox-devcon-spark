"""
Tests brewblox_devcon_spark.datastore.block_store
"""


import asyncio
from datetime import timedelta
from unittest.mock import ANY

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from pytest_httpx import HTTPXMock
from pytest_mock import MockerFixture

from brewblox_devcon_spark import const, utils
from brewblox_devcon_spark.datastore import block_store
from brewblox_devcon_spark.models import TwinKeyEntry

TESTED = block_store.__name__


def read_objects() -> list[TwinKeyEntry]:
    return block_store.SYS_OBJECTS[:1] + [
        TwinKeyEntry(keys=(f'key{i}', i+const.USER_NID_START), data={})
        for i in range(10)
    ]


@pytest.fixture
def app(mocker: MockerFixture) -> FastAPI:
    mocker.patch(TESTED + '.FLUSH_DELAY', timedelta())
    mocker.patch(TESTED + '.READY_TIMEOUT', timedelta(milliseconds=1))
    block_store.setup()
    return FastAPI()


async def test_load_save(client: AsyncClient, httpx_mock: HTTPXMock):
    config = utils.get_config()
    store = block_store.CV.get()

    default_length = len(block_store.SYS_OBJECTS)
    read_length = default_length + len(read_objects()) - 1  # overlapping item is merged

    assert len(store.items()) == default_length

    # Can't save before loading
    with pytest.raises(asyncio.TimeoutError):
        await store.save()

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

    await store.load('5678')
    assert len(store.items()) == read_length

    # Flush on insert
    store['inserted', 9001] = {}
    assert len(store.items()) == read_length + 1
    await store.run(True)
    await store.run(False)

    # Flush on remove
    del store['inserted', 9001]
    assert len(store.items()) == read_length
    await store.run(True)
    await store.run(False)


async def test_load_error(client: AsyncClient, httpx_mock: HTTPXMock, caplog: pytest.LogCaptureFixture):
    config = utils.get_config()
    store = block_store.CV.get()

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
    assert len(store.items()) == len(block_store.SYS_OBJECTS)
