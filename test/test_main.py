"""
Tests brewblox_devcon_spark.__main__.py
"""

import pytest
from brewblox_service import http, mqtt, scheduler

from brewblox_devcon_spark import __main__ as main
from brewblox_devcon_spark import (backup_storage, block_store, broadcaster,
                                   codec, commander, connection, controller,
                                   global_store, service_status, service_store,
                                   synchronization, time_sync)

TESTED = main.__name__


@pytest.fixture(autouse=True)
def mocked_parse(mocker, app_ini):
    m = mocker.patch(TESTED + '.parse_ini')
    m.return_value = app_ini
    return m


def test_main(mocker, app):
    mocker.patch(TESTED + '.service.run')
    mocker.patch(TESTED + '.service.create_app').return_value = app

    main.main()

    assert None not in [
        scheduler.fget(app),
        mqtt.handler(app),
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
def test_simulation(auto_id, mocker, app):
    app['config']['device_id'] = None
    app['config']['mock'] = auto_id
    app['config']['simulation'] = auto_id
    mocker.patch(TESTED + '.service.run')
    mocker.patch(TESTED + '.service.create_app').return_value = app

    main.main()
    assert bool(app['config']['device_id']) is auto_id
