"""
Tests brewblox_devcon_spark.__main__.py
"""

import pytest
from brewblox_service import http, mqtt, scheduler, service

from brewblox_devcon_spark import __main__ as main
from brewblox_devcon_spark import (backup_storage, block_store, broadcaster,
                                   codec, commander, connection, controller,
                                   global_store, service_status, service_store,
                                   synchronization, time_sync)
from brewblox_devcon_spark.models import ServiceConfig

TESTED = main.__name__


@pytest.fixture(autouse=True)
def m_firmware_ini(mocker):
    mocker.patch(TESTED + '.FIRMWARE_INI', 'firmware.ini')


@pytest.fixture
def m_service_funcs(app, mocker, event_loop):
    def dummy_run(app, setup):
        event_loop.run_until_complete(setup)

    mocker.patch(TESTED + '.service.create_config', autospec=True).return_value = app['config']
    mocker.patch(TESTED + '.service.create_app', autospec=True).return_value = app
    mocker.patch(TESTED + '.service.run_app', dummy_run)


def test_parse(app, sys_args):
    parser = main.create_parser()
    config = service.create_config(parser, model=ServiceConfig, raw_args=sys_args[1:])
    assert isinstance(config, ServiceConfig)


def test_main(app, m_service_funcs):
    main.main()

    assert None not in [
        scheduler.fget(app),
        mqtt.fget(app),
        http.fget(app),

        global_store.fget(app),
        service_store.fget(app),
        block_store.fget(app),

        service_status.fget(app),
        codec.fget(app),
        connection.fget(app),
        commander.fget(app),
        synchronization.fget(app),
        controller.fget(app),

        backup_storage.fget(app),
        broadcaster.fget(app),
        time_sync.fget(app),
    ]


@pytest.mark.parametrize('auto_id', [True, False])
def test_simulation(auto_id, app, m_service_funcs):
    config = utils.get_config()
    config.device_id = None
    config.mock = auto_id
    config.simulation = auto_id

    main.main()
    assert bool(config.device_id) is auto_id
