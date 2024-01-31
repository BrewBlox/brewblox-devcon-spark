import asyncio
from contextlib import AsyncExitStack, asynccontextmanager

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from pytest_mock import MockerFixture

from brewblox_devcon_spark import (codec, command, connection,
                                   datastore_blocks, datastore_settings,
                                   exceptions, mqtt, spark_api, state_machine,
                                   synchronization, utils)
from brewblox_devcon_spark.endpoints import mqtt_blocks
from brewblox_devcon_spark.models import Block, BlockIdentity

TESTED = mqtt_blocks.__name__


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(mqtt.lifespan())
        await stack.enter_async_context(connection.lifespan())
        await stack.enter_async_context(synchronization.lifespan())
        yield


@pytest.fixture
def app() -> FastAPI:
    config = utils.get_config()
    config.mock = True

    mqtt.setup()
    state_machine.setup()
    datastore_settings.setup()
    datastore_blocks.setup()
    codec.setup()
    connection.setup()
    command.setup()
    spark_api.setup()
    mqtt_blocks.setup()
    return FastAPI(lifespan=lifespan)


@pytest.fixture(autouse=True)
async def manager(manager: LifespanManager):
    yield manager


def block_args():
    config = utils.get_config()
    return Block(
        id='testobj',
        serviceId=config.name,
        type='TempSensorOneWire',
        data={
            'value': 12345,
            'offset': 20,
            'address': 'FF'
        }
    )


async def test_crud(mocker: MockerFixture):
    config = utils.get_config()
    mqtt_client = mqtt.CV.get()
    api = spark_api.CV.get()

    def publish(endpoint: str, args: Block | BlockIdentity):
        mqtt_client.publish(config.blocks_topic + endpoint, args.model_dump(mode='json'))

    def wrap(name: str) -> asyncio.Event:
        """
        Transparently wraps function in controller.
        As a side effect, an event is set.
        This allows us to get a callback on function call.
        """
        func = getattr(api, name)
        ev = asyncio.Event()

        async def wrapper(*args, **kwargs):
            retv = await func(*args, **kwargs)
            ev.set()
            return retv

        setattr(api, name, wrapper)
        return ev

    create_ev = wrap('create_block')
    write_ev = wrap('write_block')
    patch_ev = wrap('patch_block')
    delete_ev = wrap('delete_block')

    dummy = Block(
        id='dummy',
        serviceId='other',
        type='TempSensorOneWire',
        data={
            'value': 12345,
            'offset': 20,
            'address': 'FF'
        }
    )

    real = Block(
        id='real',
        serviceId=config.name,
        type='TempSensorOneWire',
        data={
            'value': 12345,
            'offset': 20,
            'address': 'FF'
        }
    )

    publish('/create', dummy)
    publish('/create', real)
    await asyncio.wait_for(create_ev.wait(), timeout=5)
    create_ev.clear()

    assert await api.read_block(BlockIdentity(id=real.id))
    with pytest.raises(exceptions.UnknownId):
        await api.read_block(BlockIdentity(id=dummy.id))

    publish('/write', dummy)
    publish('/write', real)
    await asyncio.wait_for(write_ev.wait(), timeout=5)
    write_ev.clear()

    assert await api.read_block(BlockIdentity(id=real.id))
    with pytest.raises(exceptions.UnknownId):
        await api.read_block(BlockIdentity(id=dummy.id))

    publish('/patch', dummy)
    publish('/patch', real)
    await asyncio.wait_for(patch_ev.wait(), timeout=5)
    patch_ev.clear()

    assert await api.read_block(BlockIdentity(id=real.id))
    with pytest.raises(exceptions.UnknownId):
        await api.read_block(BlockIdentity(id=dummy.id))

    publish('/delete', dummy)
    publish('/delete', real)
    await asyncio.wait_for(delete_ev.wait(), timeout=5)
    delete_ev.clear()

    with pytest.raises(exceptions.UnknownId):
        assert await api.read_block(BlockIdentity(id=real.id))
    with pytest.raises(exceptions.UnknownId):
        await api.read_block(BlockIdentity(id=dummy.id))

    assert not create_ev.is_set()
    assert not write_ev.is_set()
    assert not patch_ev.is_set()
    assert not delete_ev.is_set()
