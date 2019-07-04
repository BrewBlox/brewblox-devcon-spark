"""
Tests brewblox_devcon_spark.__main__.py
"""

import pytest
from brewblox_service import events, service

from brewblox_devcon_spark import __main__ as main
from brewblox_devcon_spark import (broadcaster, commander, commander_sim,
                                   datastore, device)

TESTED = main.__name__


@pytest.fixture(autouse=True)
def mocked_parse(mocker, app_ini):
    m = mocker.patch(TESTED + '.parse_ini')
    m.return_value = app_ini
    return m


@pytest.fixture
def list_device_app(sys_args):
    sys_args.append('--list-devices')
    parser = main.create_parser('default')
    app = service.create_app(parser=parser, raw_args=sys_args[1:])
    return app


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


def test_list_devices(mocker, list_device_app):
    mocker.patch(TESTED + '.service.create_app').return_value = list_device_app
    run_mock = mocker.patch(TESTED + '.service.run')
    all_ports_mock = mocker.patch(TESTED + '.communication.all_ports')
    all_ports_mock.return_value = [['val1', 'val2'], ['val3']]

    main.main()

    assert all_ports_mock.call_count == 1
    assert run_mock.call_count == 0


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
