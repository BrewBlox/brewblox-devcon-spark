"""
Tests brewblox_devcon_spark.__main__.py
"""

import pytest
from brewblox_devcon_spark import __main__ as main
from brewblox_devcon_spark import commander, commander_sim, datastore, device, broadcaster
from brewblox_service import events

TESTED = main.__name__


def test_main(mocker, app):
    mocker.patch(TESTED + '.service.run')
    mocker.patch(TESTED + '.service.create_app').return_value = app

    main.main()

    assert all([
        commander.get_commander(app),
        datastore.get_object_store(app),
        device.get_controller(app),
        events.get_listener(app),
        broadcaster.get_broadcaster(app)
    ])


@pytest.mark.parametrize('simulation', [True, False])
def test_simulation(simulation, mocker, app):
    app['config']['simulation'] = simulation
    mocker.patch(TESTED + '.service.run')
    mocker.patch(TESTED + '.service.create_app').return_value = app

    main.main()

    assert simulation == isinstance(
        commander.get_commander(app),
        commander_sim.SimulationCommander
    )
