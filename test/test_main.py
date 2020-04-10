"""
Tests brewblox_devcon_spark.__main__.py
"""

import pytest
from brewblox_service import events

from brewblox_devcon_spark import __main__ as main
from brewblox_devcon_spark import (broadcaster, commander, datastore, device,
                                   simulator)

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
        commander.get_commander(app),
        datastore.get_datastore(app),
        device.get_controller(app),
        events.get_listener(app),
        broadcaster.get_broadcaster(app)
    ]


@pytest.mark.parametrize('simulation', [True, False])
def test_simulation(simulation, mocker, app):
    app['config']['simulation'] = simulation
    mocker.patch(TESTED + '.service.run')
    mocker.patch(TESTED + '.service.create_app').return_value = app

    main.main()

    if simulation:
        assert simulator.get_simulator(app) is not None
    else:
        with pytest.raises(KeyError):
            simulator.get_simulator(app)
