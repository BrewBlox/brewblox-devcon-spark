"""
Tests brewblox_devcon_spark.__main__.py
"""

import pytest
from brewblox_service import mqtt

from brewblox_devcon_spark import __main__ as main
from brewblox_devcon_spark import (block_store, broadcaster, commander,
                                   controller, service_store)

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
        commander.fget(app),
        service_store.fget(app),
        block_store.fget(app),
        controller.fget(app),
        mqtt.handler(app),
        broadcaster.fget(app)
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
