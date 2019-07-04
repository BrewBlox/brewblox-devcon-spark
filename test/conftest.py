"""
Master file for pytest fixtures.
Any fixtures declared here are available to all test functions in this directory.
"""


import logging

import pytest
from brewblox_service import brewblox_logger, features, service

from brewblox_devcon_spark.__main__ import create_parser

LOGGER = brewblox_logger(__name__)


@pytest.fixture(scope='session', autouse=True)
def log_enabled():
    """Sets log level to DEBUG for all test functions.
    Allows all logged messages to be captured during pytest runs"""
    logging.getLogger().setLevel(logging.DEBUG)
    logging.captureWarnings(True)


@pytest.fixture
def app_config() -> dict:
    return {
        'name': 'test_app',
        'host': 'localhost',
        'port': 1234,
        'debug': True,
        'device_serial': '/dev/TESTEH',
        'device_id': '1234',
        'discovery': 'all',
        'simulation': False,
        'broadcast_interval': 5,
        'broadcast_exchange': 'brewcast',
        'sync_exchange': 'syncast',
        'mdns_host': '172.17.0.1',
        'mdns_port': 5000,
        'volatile': True,
    }


@pytest.fixture
def sys_args(app_config) -> list:
    return [str(v) for v in [
        'app_name',
        '--debug',
        '--name', app_config['name'],
        '--host', app_config['host'],
        '--port', app_config['port'],
        '--device-serial', app_config['device_serial'],
        '--device-id', app_config['device_id'],
        '--discovery', app_config['discovery'],
        '--broadcast-interval', app_config['broadcast_interval'],
        '--broadcast-exchange', app_config['broadcast_exchange'],
        '--sync-exchange', app_config['sync_exchange'],
        '--mdns-host', app_config['mdns_host'],
        '--mdns-port', app_config['mdns_port'],
        '--volatile'
    ]]


@pytest.fixture
def app_ini() -> dict:
    return {
        'proto_version': '3f2243a',
        'proto_date': '2019-06-06',
        'firmware_version': 'd264dc6c',
        'firmware_date': '2019-07-03',
    }


@pytest.fixture
def event_loop(loop):
    # aresponses uses the "event_loop" fixture
    # this makes loop available under either name
    yield loop


@pytest.fixture
def app(sys_args, app_ini):
    parser = create_parser('default')
    app = service.create_app(parser=parser, raw_args=sys_args[1:])
    app['ini'] = app_ini
    return app


@pytest.fixture
def client(app, aiohttp_client, loop):
    """Allows patching the app or aiohttp_client before yielding it.

    Any tests wishing to add custom behavior to app can override the fixture
    """
    LOGGER.debug('Available features:')
    for name, impl in app.get(features.FEATURES_KEY, {}).items():
        LOGGER.debug(f'Feature "{name}" = {impl}')
    LOGGER.debug(app.on_startup)

    return loop.run_until_complete(aiohttp_client(app))


@pytest.fixture
def spark_blocks():
    return [
        {
            'id': 'balancer-1',
            'nid': 200,
            'groups': [0],
            'type': 'Balancer',
            'data': {}
        },
        {
            'id': 'mutex-1',
            'nid': 300,
            'groups': [0],
            'type': 'Mutex',
            'data': {
                'differentActuatorWait': 43
            }
        },
        {
            'id': 'group-1',
            'nid': 201,
            'groups': [0],
            'type': 'SetpointProfile',
            'data': {
                'points': [
                    {
                        'time': 1540376829,
                        'temperature[degC]': 0
                    },
                    {
                        'time': 1540376839,
                        'temperature[degC]': 50
                    },
                    {
                        'time': 1540376849,
                        'temperature[degC]': 100
                    }
                ],
                'targetId<>': 'setpoint-sensor-pair-2'
            }
        },
        {
            'id': 'sensor-1',
            'nid': 202,
            'groups': [0],
            'type': 'TempSensorMock',
            'data': {
                'value[celsius]': 20.89789201,
                'connected': True
            }
        },
        {
            'id': 'sensor-onewire-1',
            'nid': 203,
            'groups': [0],
            'type': 'TempSensorOneWire',
            'data': {
                'value[celsius]': 20.89789201,
                'offset[delta_degC]': 9,
                'address': 'DEADBEEF'
            }
        },
        {
            'id': 'setpoint-sensor-pair-1',
            'nid': 204,
            'groups': [0],
            'type': 'SetpointSensorPair',
            'data': {
                'sensorId<>': 'sensor-1',
                'setting': 0,
                'value': 0,
                'settingEnabled': True,
                'filter': 'FILT_30s',
                'filterThreshold': 2
            }
        },
        {
            'id': 'setpoint-sensor-pair-2',
            'nid': 205,
            'groups': [0],
            'type': 'SetpointSensorPair',
            'data': {
                'sensorId<>': 0,
                'setting': 0,
                'value': 0,
                'settingEnabled': True
            }
        },
        {
            'id': 'actuator-1',
            'nid': 206,
            'groups': [0],
            'type': 'ActuatorAnalogMock',
            'data': {
                'setting': 20,
                'minSetting': 10,
                'maxSetting': 30,
                'value': 50,
                'minValue': 40,
                'maxValue': 60
            }
        },
        {
            'id': 'actuator-pwm-1',
            'nid': 207,
            'groups': [0],
            'type': 'ActuatorPwm',
            'data': {
                'constrainedBy': {
                    'constraints': [
                        {
                            'min': 5
                        },
                        {
                            'max': 50
                        },
                        {
                            'balanced<>': {
                                'balancerId<>': 'balancer-1'
                            }
                        }
                    ]
                },
                'period': 4000,
                'actuatorId<>': 'actuator-digital-1'
            }
        },
        {
            'id': 'actuator-digital-1',
            'nid': 208,
            'groups': [0],
            'type': 'DigitalActuator',
            'data': {
                'channel': 1,
                'constrainedBy': {
                    'constraints': [
                        {
                            'mutex<>': 'mutex-1'
                        }
                    ]
                }
            }
        },
        {
            'id': 'offset-1',
            'nid': 209,
            'groups': [0],
            'type': 'ActuatorOffset',
            'data': {
                'targetId<>': 'setpoint-sensor-pair-1',
                'referenceId<>': 'setpoint-sensor-pair-1'
            }
        },
        {
            'id': 'pid-1',
            'nid': 210,
            'groups': [0],
            'type': 'Pid',
            'data': {
                'inputId<>': 'setpoint-sensor-pair-1',
                'outputId<>': 'actuator-pwm-1',
                'enabled': True,
                'active': True,
                'kp': 20,
                'ti': 3600,
                'td': 60
            }
        },
        {
            'id': 'DisplaySettings',
            'nid': 7,
            'groups': [7],
            'type': 'DisplaySettings',
            'data': {
                'widgets': [
                    {
                        'pos': 1,
                        'color': '0088aa',
                        'name': 'pwm1',
                        'actuatorAnalog<>': 'actuator-pwm-1'
                    },
                    {
                        'pos': 2,
                        'color': '00aa88',
                        'name': 'pair1',
                        'setpointSensorPair<>': 'setpoint-sensor-pair-1'
                    },
                    {
                        'pos': 3,
                        'color': 'aa0088',
                        'name': 'sensor1',
                        'tempSensor<>': 'sensor-1'
                    },
                    {
                        'pos': 4,
                        'color': 'aa8800',
                        'name': 'pid',
                        'pid<>': 'pid-1'
                    }
                ],
                'name': 'test'
            }
        },
        {
            'id': 'ds2413-hw-1',
            'nid': 211,
            'groups': [0, 1, 2, 3, 4, 5, 6],
            'type': 'DS2413',
            'data': {
                'address': '4444444444444444'
            }
        },
        {
            'id': 'ow-act',
            'nid': 212,
            'groups': [0, 1, 2, 3, 4, 5, 6],
            'type': 'DigitalActuator',
            'data': {
                'channel': 1,
                'invert': True,
                'hwDevice<DS2413>': 'ds2413-hw-1'
            }
        }
    ]
