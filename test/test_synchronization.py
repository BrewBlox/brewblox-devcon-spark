"""
Tests brewblox_devcon_spark.synchronization
"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from brewblox_service import brewblox_logger, scheduler

from brewblox_devcon_spark import (block_store, codec, commander, connection,
                                   exceptions, global_store, service_status,
                                   service_store, synchronization)
from brewblox_devcon_spark.models import ServiceStatusDescription

TESTED = synchronization.__name__
LOGGER = brewblox_logger(__name__)


def states(app):
    status = service_status.fget(app)
    return [
        status.disconnected_ev.is_set(),
        status.connected_ev.is_set(),
        status.acknowledged_ev.is_set(),
        status.synchronized_ev.is_set(),
    ]


async def connect(app) -> synchronization.SparkSynchronization:
    service_status.set_enabled(app, True)
    await service_status.wait_connected(app)
    s = synchronization.SparkSynchronization(app)
    await s.synchronize()
    await service_status.wait_synchronized(app)
    return s


async def disconnect(app):
    service_status.set_enabled(app, False)
    await connection.fget(app).start_reconnect()
    await service_status.wait_disconnected(app)


@pytest.fixture
async def app(app, event_loop):
    app['config']['isolated'] = True
    scheduler.setup(app)
    service_status.setup(app)
    codec.setup(app)
    connection.setup(app)
    commander.setup(app)
    global_store.setup(app)
    service_store.setup(app)
    block_store.setup(app)
    return app


async def test_sync_status(app, client):
    await connect(app)
    assert states(app) == [False, True, True, True]

    await disconnect(app)
    assert states(app) == [True, False, False, False]

    await connect(app)
    assert states(app) == [False, True, True, True]


async def test_sync_errors(app, client, mocker):
    mocker.patch(TESTED + '.datastore.check_remote', autospec=True, side_effect=RuntimeError)

    with pytest.raises(RuntimeError):
        await connect(app)

    assert states(app) == [False, True, True, False]


async def test_write_error(app, client, mocker):
    mocker.patch.object(commander.fget(app), 'patch_block', autospec=True, side_effect=RuntimeError)

    with pytest.raises(RuntimeError):
        await connect(app)

    assert states(app) == [False, True, True, False]


async def test_timeout(app, client, mocker):
    mocker.patch(TESTED + '.HANDSHAKE_TIMEOUT_S', 0.1)
    mocker.patch.object(commander.fget(app), 'version', AsyncMock(side_effect=RuntimeError))

    with pytest.raises(asyncio.TimeoutError):
        await connect(app)


async def test_device_name(app, client):
    s = await connect(app)
    assert s.device_name == app['config']['device_id']

    app['config']['simulation'] = True
    assert s.device_name.startswith('simulator__')


async def test_on_global_store_change(app, client):
    # Update during runtime
    s = await connect(app)
    global_store.fget(app).units['temperature'] = 'degF'
    global_store.fget(app).time_zone['posixValue'] = 'Africa/Casablanca'
    await s.on_global_store_change()

    # Should safely handle disconnected state
    await disconnect(app)
    await s.on_global_store_change()


async def test_incompatible_error(app, client, mocker):
    m_desc: ServiceStatusDescription = mocker.patch(TESTED + '.service_status.desc').return_value
    m_desc.firmware_error = 'INCOMPATIBLE'
    m_desc.identity_error = None

    with pytest.raises(exceptions.IncompatibleFirmware):
        await connect(app)
    assert states(app) == [False, True, True, False]

    # run() catches IncompatibleFirmware
    with pytest.raises(asyncio.TimeoutError):
        s = synchronization.SparkSynchronization(app)
        await asyncio.wait_for(s.run(), timeout=0.2)


async def test_invalid_error(app, client, mocker):
    m_desc: ServiceStatusDescription = mocker.patch(TESTED + '.service_status.desc').return_value
    m_desc.firmware_error = None
    m_desc.identity_error = 'INVALID'

    with pytest.raises(exceptions.InvalidDeviceId):
        await connect(app)
    assert states(app) == [False, True, True, False]

    # run() catches InvalidDeviceId
    with pytest.raises(asyncio.TimeoutError):
        s = synchronization.SparkSynchronization(app)
        await asyncio.wait_for(s.run(), timeout=0.2)
