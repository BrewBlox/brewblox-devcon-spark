"""
Tests brewblox_devcon_spark.synchronization
"""

import asyncio

import pytest
from brewblox_service import brewblox_logger, repeater, scheduler
from mock import AsyncMock

from brewblox_devcon_spark import (commander_sim, datastore, device, state,
                                   synchronization)
from brewblox_devcon_spark.codec import codec, unit_conversion

TESTED = synchronization.__name__
LOGGER = brewblox_logger(__name__)


def states(app):
    events = state._events(app)
    return [
        events.disconnect_ev.is_set(),
        events.connect_ev.is_set(),
        events.synchronize_ev.is_set(),
    ]


async def connect(app):
    await state.set_connect(app, 'synchronization test')
    await synchronization.get_syncher(app).sync_done.wait()
    await asyncio.sleep(0.01)


async def disconnect(app):
    await state.set_disconnect(app)
    await state.wait_disconnect(app)
    await asyncio.sleep(0.01)


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
    state.setup(app)
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
    m = mocker.patch(TESTED + '.object_api.ObjectApi').return_value
    m.read = AsyncMock()
    m.write = AsyncMock()
    return m


@pytest.fixture
def syncher(app):
    return synchronization.get_syncher(app)


async def test_sync_status(app, client, mocker):
    await state.wait_synchronize(app)
    assert states(app) == [False, True, True]

    await disconnect(app)
    assert states(app) == [True, False, False]

    await connect(app)
    assert states(app) == [False, True, True]


async def test_sync_cancel(app, client, syncher):
    await syncher.end()
    assert not syncher.active


async def test_sync_errors(app, client, mocker, system_exit_mock):
    await state.wait_synchronize(app)
    mocker.patch(TESTED + '.datastore.check_remote', AsyncMock(side_effect=RuntimeError))

    await disconnect(app)
    await connect(app)

    assert states(app) == [False, True, False]
    assert system_exit_mock.call_count == 1
    assert not synchronization.get_syncher(app).active


async def test_write_error(app, client, mocker, api_mock, system_exit_mock):
    await state.wait_synchronize(app)
    api_mock.write = AsyncMock(side_effect=RuntimeError)
    await disconnect(app)
    await connect(app)

    assert states(app) == [False, True, False]
    assert system_exit_mock.call_count == 1
    assert not synchronization.get_syncher(app).active


async def test_timeout(app, client, syncher, mocker, system_exit_mock):
    async def m_wait_handshake(app):
        return False
    await state.wait_synchronize(app)
    await disconnect(app)
    mocker.patch(TESTED + '.HANDSHAKE_TIMEOUT_S', 0.0001)
    mocker.patch(TESTED + '.state.wait_handshake', side_effect=m_wait_handshake)

    await connect(app)
    assert system_exit_mock.call_count == 1
    assert not syncher.active


async def test_device_name(app, client, syncher):
    await state.wait_synchronize(app)
    assert syncher.device_name == app['config']['device_id']

    app['config']['simulation'] = True
    assert syncher.device_name.startswith('simulator__')


async def test_user_units(app, client, syncher):
    await state.wait_synchronize(app)
    assert syncher.get_user_units() == {'Temp': 'degC'}
    assert await syncher.set_user_units({'Temp': 'degF'}) == {'Temp': 'degF'}
    assert syncher.get_user_units() == {'Temp': 'degF'}

    assert await syncher.set_user_units({'Temp': 'lava'}) == {'Temp': 'degF'}


async def test_autoconnecting(app, client, syncher):
    await state.wait_synchronize(app)
    assert syncher.get_autoconnecting() is True
    assert await syncher.set_autoconnecting(False) is False
    assert syncher.get_autoconnecting() is False
    assert await state.wait_autoconnecting(app, False) is False


async def test_errors(app, client, syncher, mocker, system_exit_mock):
    m_summary = mocker.patch(TESTED + '.state.summary').return_value
    await state.wait_synchronize(app)

    m_summary.compatible = False
    m_summary.valid = True
    await disconnect(app)
    await connect(app)
    assert syncher.active
    assert states(app) == [False, True, False]

    m_summary.compatible = True
    m_summary.valid = False
    await disconnect(app)
    await connect(app)
    assert syncher.active
    assert states(app) == [False, True, False]


async def test_migrate(app, client, syncher, mocker):
    await state.wait_synchronize(app)
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
