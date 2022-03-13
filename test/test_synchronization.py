"""
Tests brewblox_devcon_spark.synchronization
"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from brewblox_service import brewblox_logger, scheduler

from brewblox_devcon_spark import (block_store, codec, commander,
                                   connection_sim, global_store,
                                   service_status, service_store,
                                   synchronization)
from brewblox_devcon_spark.service_status import StatusDescription

TESTED = synchronization.__name__
LOGGER = brewblox_logger(__name__)


def states(app):
    status = service_status.fget(app)
    return [
        status.disconnected_ev.is_set(),
        status.connected_ev.is_set(),
        status.synchronized_ev.is_set(),
    ]


async def connect(app, syncher):
    service_status.set_connected(app, 'synchronization test')
    await syncher.run()
    await asyncio.sleep(0.01)


async def disconnect(app):
    service_status.set_disconnected(app)
    await service_status.wait_disconnected(app)
    await asyncio.sleep(0.01)


@pytest.fixture(autouse=True)
def m_timedelta(mocker):
    mocker.patch(TESTED + '.timedelta', autospec=True)


@pytest.fixture(autouse=True)
def ping_interval_mock(mocker):
    mocker.patch(TESTED + '.PING_INTERVAL_S', 0.0001)


@pytest.fixture
async def app(app, loop):
    app['config']['volatile'] = True
    scheduler.setup(app)
    service_status.setup(app)
    codec.setup(app)
    connection_sim.setup(app)
    commander.setup(app)
    global_store.setup(app)
    service_store.setup(app)
    block_store.setup(app)
    return app


@pytest.fixture
async def syncher(app, client, mocker):
    mocker.patch(TESTED + '.service_status.wait_disconnected', autospec=True)
    s = synchronization.SparkSynchronization(app)
    await s.prepare()
    return s


async def test_sync_status(app, client, syncher):
    await syncher.run()
    assert states(app) == [False, True, True]

    await disconnect(app)
    assert states(app) == [True, False, False]

    await connect(app, syncher)
    assert states(app) == [False, True, True]


async def test_sync_errors(app, client, syncher, mocker):
    mocker.patch(TESTED + '.datastore.check_remote', autospec=True, side_effect=RuntimeError)

    await disconnect(app)
    with pytest.raises(RuntimeError):
        await connect(app, syncher)

    assert states(app) == [False, True, False]


async def test_write_error(app, client, syncher, mocker):
    mocker.patch.object(commander.fget(app), 'write_object', autospec=True, side_effect=RuntimeError)
    await disconnect(app)
    with pytest.raises(RuntimeError):
        await connect(app, syncher)

    assert states(app) == [False, True, False]


async def test_timeout(app, client, syncher, mocker):
    async def m_wait_ack(app, wait=True):
        if wait:
            await asyncio.sleep(1)
        return False
    await disconnect(app)
    await syncher.end()
    mocker.patch(TESTED + '.HANDSHAKE_TIMEOUT_S', 0.1)
    mocker.patch(TESTED + '.PING_INTERVAL_S', 0.0001)
    mocker.patch(TESTED + '.service_status.wait_acknowledged', autospec=True, side_effect=m_wait_ack)
    mocker.patch.object(commander.fget(app), 'noop', AsyncMock(side_effect=RuntimeError))

    service_status.set_connected(app, 'timeout test')
    with pytest.raises(asyncio.TimeoutError):
        await syncher.run()


async def test_device_name(app, client, syncher):
    await syncher.run()
    assert syncher.device_name == app['config']['device_id']

    app['config']['simulation'] = True
    assert syncher.device_name.startswith('simulator__')


async def test_autoconnecting(app, client, syncher):
    await syncher.run()
    assert syncher.get_autoconnecting() is True
    assert await syncher.set_autoconnecting(False) is False
    assert syncher.get_autoconnecting() is False
    assert await service_status.wait_autoconnecting(app, False) is False


async def test_on_global_store_change(app, client, syncher):
    # Update during runtime
    await syncher.run()
    global_store.fget(app).units['temperature'] = 'degF'
    await syncher.on_global_store_change()

    # Should safely handle disconnected state
    await disconnect(app)
    await syncher.on_global_store_change()


async def test_errors(app, client, syncher, mocker):
    m_desc: StatusDescription = mocker.patch(TESTED + '.service_status.desc').return_value
    await syncher.run()

    m_desc.handshake_info.is_compatible_firmware = False
    m_desc.handshake_info.is_valid_device_id = True
    await disconnect(app)
    await connect(app, syncher)
    assert states(app) == [False, True, False]

    m_desc.handshake_info.is_compatible_firmware = True
    m_desc.handshake_info.is_valid_device_id = False
    await disconnect(app)
    await connect(app, syncher)
    assert states(app) == [False, True, False]
