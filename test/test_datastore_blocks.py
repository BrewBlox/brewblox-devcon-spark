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

from brewblox_devcon_spark import (const, datastore_blocks, exceptions,
                                   state_machine, utils)
from brewblox_devcon_spark.models import (ControllerDescription,
                                          DeviceDescription, TwinKeyEntry)

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

    state_machine.setup()
    datastore_blocks.setup()
    return FastAPI()


@pytest.fixture(autouse=True)
async def manager(manager: LifespanManager):
    yield manager


async def test_load_flush(httpx_mock: HTTPXMock):
    config = utils.get_config()
    state = state_machine.CV.get()
    store = datastore_blocks.CV.get()

    default_length = len(datastore_blocks.SYS_OBJECTS)
    read_length = default_length + len(read_objects()) - 1  # overlapping item is merged

    assert len(store.items()) == 0

    # Invalid format
    httpx_mock.add_response(url=f'{config.datastore_url}/get',
                            match_json={'id': f'mock__{config.name}-blocks-db',
                                        'namespace': const.SERVICE_NAMESPACE},
                            json={})

    httpx_mock.add_response(url=f'{config.datastore_url}/get',
                            match_json={'id': f'mock__{config.name}-blocks-db',
                                        'namespace': const.SERVICE_NAMESPACE},
                            json={
                                'value': {
                                    'id': f'mock__{config.name}-blocks-db',
                                    'namespace': const.SERVICE_NAMESPACE,
                                    'data': [v.model_dump(mode='json')
                                             for v in read_objects()],
                                },
                            })

    httpx_mock.add_response(url=f'{config.datastore_url}/set',
                            match_json={
                                'value': {
                                    'id': f'mock__{config.name}-blocks-db',
                                    'namespace': const.SERVICE_NAMESPACE,
                                    'data': ANY
                                },
                            })

    async with asyncio.timeout(10):
        # Can't load before acknowledged
        with pytest.raises(exceptions.NotConnected):
            await store.load()

        # Can't flush before acknowledged
        with pytest.raises(exceptions.NotConnected):
            await store.flush()

        state.set_enabled(True)
        state.set_connected('MOCK', '')
        state.set_acknowledged(ControllerDescription(
            system_version='',
            platform='mock',
            reset_reason='',
            firmware=state.desc().service.firmware.model_copy(),
            device=DeviceDescription(device_id='1234'),
        ))

        # First attempt gets invalid data, and falls back on defaults
        await store.load()
        assert len(store.items()) == default_length

        await store.load()
        assert len(store.items()) == read_length

        # flush on insert
        store['inserted', 9001] = {}
        assert len(store.items()) == read_length + 1
        await store.flush()

        # Flush on remove
        del store['inserted', 9001]
        assert len(store.items()) == read_length
        await store.flush()

        # Does nothing if not changed
        await store.flush()

        assert len(httpx_mock.get_requests(url=f'{config.datastore_url}/set')) == 2


async def test_load_error(httpx_mock: HTTPXMock):
    config = utils.get_config()
    state = state_machine.CV.get()
    store = datastore_blocks.CV.get()

    httpx_mock.add_response(url=f'{config.datastore_url}/get',
                            match_json={'id': '1234-blocks-db',
                                        'namespace': const.SERVICE_NAMESPACE},
                            json={
                                'value': {
                                    'id': '1234-blocks-db',
                                    'namespace': const.SERVICE_NAMESPACE,
                                    'data': 'miniaturized giant hamsters from outer space',
                                },
                            })

    # Removed after load
    store['inserted', 9001] = {}

    state.set_enabled(True)
    state.set_connected('TCP', '')
    state.set_acknowledged(ControllerDescription(
        system_version='',
        platform='dummy',
        reset_reason='',
        firmware=state.desc().service.firmware.model_copy(),
        device=DeviceDescription(device_id='1234'),
    ))

    async with asyncio.timeout(10):
        await store.load()
        assert len(store.items()) == len(datastore_blocks.SYS_OBJECTS)
