"""
Tests brewblox_devcon_spark.time_sync
"""

import asyncio

import pytest
from brewblox_service import repeater, scheduler

from brewblox_devcon_spark import (block_store, codec, commander, connection,
                                   controller, global_store, service_status,
                                   service_store, synchronization, time_sync)
from brewblox_devcon_spark.models import ServiceConfig

TESTED = time_sync.__name__


@pytest.fixture(autouse=True)
def m_error_interval(mocker):
    mocker.patch(TESTED + '.ERROR_INTERVAL_S', 0.01)


@pytest.fixture
def m_controller(mocker):
    m = mocker.patch(TESTED + '.controller.fget')
    return m.return_value


@pytest.fixture
async def setup(app):
    config: ServiceConfig = app['config']
    config.time_sync_interval = 0.01

    service_status.setup(app)
    scheduler.setup(app)
    codec.setup(app)
    block_store.setup(app)
    global_store.setup(app)
    service_store.setup(app)
    connection.setup(app)
    commander.setup(app)
    synchronization.setup(app)
    controller.setup(app)
    time_sync.setup(app)


@pytest.fixture
async def synchronized(app, client):
    await service_status.wait_synchronized(app)


async def test_sync(app, client, synchronized, m_controller):
    await asyncio.sleep(0.1)
    assert time_sync.fget(app).enabled
    assert m_controller.patch_block.call_count > 0


async def test_disabled_sync(app, client, synchronized):
    app['config'].time_sync_interval = 0

    sync = time_sync.TimeSync(app)
    with pytest.raises(repeater.RepeaterCancelled):
        await sync.prepare()

    assert not sync.enabled
    assert not sync.active
