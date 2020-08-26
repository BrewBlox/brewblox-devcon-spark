"""
Tests brewblox_devcon_spark.synchronization
"""

import asyncio

import pytest
from brewblox_service import brewblox_logger, repeater, scheduler
from mock import AsyncMock

from brewblox_devcon_spark import (commander_sim, datastore, device,
                                   service_status, synchronization)
from brewblox_devcon_spark.codec import codec, unit_conversion
from brewblox_devcon_spark.service_status import StatusDescription

TESTED = synchronization.__name__
LOGGER = brewblox_logger(__name__)


def states(app):
    status = service_status.get_status(app)
    return [
        status.disconnected_ev.is_set(),
        status.connected_ev.is_set(),
        status.synchronized_ev.is_set(),
    ]


async def connect(app):
    service_status.set_connected(app, 'synchronization test')
    await synchronization.get_syncher(app).sync_done.wait()
    await asyncio.sleep(0.01)


async def disconnect(app):
    service_status.set_disconnected(app)
    await service_status.wait_disconnected(app)
    await asyncio.sleep(0.01)


async def wait_sync(app):
    await asyncio.wait_for(service_status.wait_synchronized(app), 10)


@pytest.fixture(autouse=True)
def m_timedelta(mocker):
    mocker.patch(TESTED + '.timedelta')


@pytest.fixture(autouse=True)
def ping_interval_mock(mocker):
    mocker.patch(TESTED + '.PING_INTERVAL_S', 0.0001)


@pytest.fixture(autouse=True)
def system_exit_mock(mocker):
    m = mocker.patch(TESTED + '.web.GracefulExit',
                     side_effect=repeater.RepeaterCancelled)
    return m


@pytest.fixture
async def app(app, loop):
    app['config']['volatile'] = True
    service_status.setup(app)
    scheduler.setup(app)
    datastore.setup(app)
    commander_sim.setup(app)
    unit_conversion.setup(app)
    codec.setup(app)
    device.setup(app)
    synchronization.setup(app)
    return app


@pytest.fixture
async def block_store(app, loop):
    return datastore.get_block_store(app)


@pytest.fixture
def service_store(app):
    return datastore.get_service_store(app)


@pytest.fixture(autouse=True)
def api_mock(mocker):
    m = mocker.patch(TESTED + '.blocks_api.BlocksApi').return_value
    m.read = AsyncMock()
    m.write = AsyncMock()
    return m


@pytest.fixture
def syncher(app):
    return synchronization.get_syncher(app)


async def test_sync_status(app, client, mocker):
    await wait_sync(app)
    assert states(app) == [False, True, True]

    await disconnect(app)
    assert states(app) == [True, False, False]

    await connect(app)
    assert states(app) == [False, True, True]


async def test_sync_cancel(app, client, syncher):
    await syncher.end()
    assert not syncher.active


async def test_sync_errors(app, client, mocker, system_exit_mock):
    await wait_sync(app)
    mocker.patch(TESTED + '.datastore.check_remote', AsyncMock(side_effect=RuntimeError))

    await disconnect(app)
    await connect(app)

    assert states(app) == [False, True, False]
    assert system_exit_mock.call_count == 1
    assert not synchronization.get_syncher(app).active


async def test_write_error(app, client, mocker, api_mock, system_exit_mock):
    await wait_sync(app)
    api_mock.write = AsyncMock(side_effect=RuntimeError)
    await disconnect(app)
    await connect(app)

    assert states(app) == [False, True, False]
    assert system_exit_mock.call_count == 1
    assert not synchronization.get_syncher(app).active


async def test_timeout(app, client, syncher, mocker, system_exit_mock):
    async def m_wait_handshake(app):
        return False
    await wait_sync(app)
    await disconnect(app)
    mocker.patch(TESTED + '.HANDSHAKE_TIMEOUT_S', 0.0001)
    mocker.patch(TESTED + '.service_status.wait_acknowledged', side_effect=m_wait_handshake)

    await connect(app)
    assert system_exit_mock.call_count == 1
    assert not syncher.active


async def test_device_name(app, client, syncher):
    await wait_sync(app)
    assert syncher.device_name == app['config']['device_id']

    app['config']['simulation'] = True
    assert syncher.device_name.startswith('simulator__')


async def test_user_units(app, client, syncher):
    await wait_sync(app)
    assert syncher.get_user_units() == {'Temp': 'degC'}
    assert await syncher.set_user_units({'Temp': 'degF'}) == {'Temp': 'degF'}
    assert syncher.get_user_units() == {'Temp': 'degF'}

    assert await syncher.set_user_units({'Temp': 'lava'}) == {'Temp': 'degF'}


async def test_autoconnecting(app, client, syncher):
    await wait_sync(app)
    assert syncher.get_autoconnecting() is True
    assert await syncher.set_autoconnecting(False) is False
    assert syncher.get_autoconnecting() is False
    assert await service_status.wait_autoconnecting(app, False) is False


async def test_errors(app, client, syncher, mocker, system_exit_mock):
    m_desc: StatusDescription = mocker.patch(TESTED + '.service_status.desc').return_value
    await wait_sync(app)

    m_desc.handshake_info.is_compatible_firmware = False
    m_desc.handshake_info.is_valid_device_id = True
    await disconnect(app)
    await connect(app)
    assert syncher.active
    assert states(app) == [False, True, False]

    m_desc.handshake_info.is_compatible_firmware = True
    m_desc.handshake_info.is_valid_device_id = False
    await disconnect(app)
    await connect(app)
    assert syncher.active
    assert states(app) == [False, True, False]


async def test_migrate(app, client, syncher, mocker):
    await wait_sync(app)
    store = datastore.get_service_store(app)

    with store.open() as config:
        # Migration happened
        assert config['version'] == 'v1'

    # Should not be called - service store is read already
    mocker.patch(TESTED + '.datastore.CouchDBConfigStore',
                 side_effect=repeater.RepeaterCancelled)

    await syncher._migrate_config_store()
    assert syncher.active

    with store.open() as config:
        assert config['version'] == 'v1'


async def test_format_trace(app, client, syncher):
    await wait_sync(app)
    src = [{'action': 'UPDATE_BLOCK', 'id': 19, 'type': 319},
           {'action': 'UPDATE_BLOCK', 'id': 101, 'type': 318},
           {'action': 'UPDATE_BLOCK', 'id': 102, 'type': 301},
           {'action': 'UPDATE_BLOCK', 'id': 103, 'type': 311},
           {'action': 'UPDATE_BLOCK', 'id': 104, 'type': 302},
           {'action': 'SYSTEM_TASKS', 'id': 0, 'type': 0},
           {'action': 'UPDATE_DISPLAY', 'id': 0, 'type': 0},
           {'action': 'UPDATE_CONNECTIONS', 'id': 0, 'type': 0},
           {'action': 'WRITE_BLOCK', 'id': 2, 'type': 256},
           {'action': 'PERSIST_BLOCK', 'id': 2, 'type': 256}]
    parsed = await syncher.format_trace(src)
    assert parsed[0] == 'UPDATE_BLOCK         Spark3Pins           [SparkPins,19]'
    assert parsed[-1] == 'PERSIST_BLOCK        SysInfo              [SystemInfo,2]'
    assert parsed[5] == 'SYSTEM_TASKS'
