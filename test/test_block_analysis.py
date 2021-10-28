"""
Tests brewblox_devcon_spark.block_analysis
"""

from typing import Optional

from brewblox_devcon_spark import block_analysis


def blox_link(id: Optional[str], blockType: Optional[str] = None, driven=None):
    return {
        '__bloxtype': 'Link',
        'id': id,
        'type': blockType,
        'driven': driven,
    }


def blox_qty(value: Optional[float], unit: str = None):
    return {
        '__bloxtype': 'Quantity',
        'value': value,
        'unit': unit,
    }


def temp_qty(value: Optional[float]):
    return blox_qty(value, 'degC')


def delta_temp_qty(value: Optional[float]):
    return blox_qty(value, 'delta_degC')


def make_blocks():
    return [
        {
            'id': 'Sensor',
            'type': 'TempSensorOneWire',
            'groups': [0],
            'serviceId': 'test',
            'data': {
                'address': 'deadbeef',
                'offset': delta_temp_qty(0),
                'value': temp_qty(20),
                'oneWireBusId': blox_link(None),
            },
        },
        {
            'id': 'Setpoint',
            'type': 'SetpointSensorPair',
            'groups': [0],
            'serviceId': 'test',
            'data': {
                'sensorId': blox_link('Sensor', 'TempSensorOneWire'),
                'storedSetting': temp_qty(20),
                'setting': temp_qty(None),
                'value': temp_qty(None),
                'valueUnfiltered': temp_qty(None),
                'resetFilter': False,
                'settingEnabled': True,
                'filter': 'FILTER_15s',
                'filterThreshold': delta_temp_qty(5),
            },
        },
        {
            'id': 'Heat PID',
            'type': 'Pid',
            'groups': [0],
            'serviceId': 'test',
            'data': {
                'inputValue': temp_qty(0),
                'inputSetting': temp_qty(0),
                'outputValue': 0,
                'outputSetting': 0,
                'enabled': False,
                'active': True,
                'kp': blox_qty(20, '1 / degC'),
                'ti': blox_qty(2, 'h'),
                'td': blox_qty(0, 's'),
                'p': 0,
                'i': 0,
                'd': 0,
                'error': delta_temp_qty(0),
                'integral': blox_qty(0, 'delta_degC * hour'),
                'derivative': blox_qty(0, 'delta_degC / minute'),
                'derivativeFilter': 'FILTER_NONE',
                'integralReset': 0,
                'boilPointAdjust': delta_temp_qty(0),
                'boilMinOutput': 0,
                'boilModeActive': False,
                'inputId': blox_link('Setpoint', 'SetpointSensorPair'),
                'outputId': blox_link('Heat PWM', 'ActuatorPwm'),
                'drivenOutputId': blox_link('Heat PWM', 'ActuatorPwm', True),
            },
        },
        {
            'id': 'Heat PWM',
            'type': 'ActuatorPwm',
            'groups': [0],
            'serviceId': 'test',
            'data': {
                'constrainedBy': {'constraints': []},
                'desiredSetting': 50,
                'setting': 50,
                'value': 50,
                'actuatorId': blox_link('Heat Actuator', 'DigitalActuator'),
                'drivenActuatorId': blox_link(
                    'Heat Actuator',
                    'DigitalActuator',
                    True,
                ),
                'enabled': True,
                'period': blox_qty(10, 's'),
            },
        },
        {
            'id': 'Heat Actuator',
            'type': 'DigitalActuator',
            'groups': [0],
            'serviceId': 'test',
            'data': {
                'channel': 0,
                'constrainedBy': {
                    'constraints': [
                        {
                            'remaining': blox_qty(None, 's'),
                            'delayedOn': blox_qty(1, 'h'),
                        },
                    ],
                },
                'desiredState': 'STATE_ACTIVE',
                'state': 'STATE_ACTIVE',
                'hwDevice': blox_link('Spark Pins', 'Spark3Pins', True),
                'invert': False,
            },
        },
        {
            'id': 'Cool PID',
            'type': 'Pid',
            'groups': [0],
            'serviceId': 'test',
            'data': {
                'inputValue': temp_qty(0),
                'inputSetting': temp_qty(0),
                'outputValue': 0,
                'outputSetting': 0,
                'enabled': False,
                'active': True,
                'kp': blox_qty(20, '1 / degC'),
                'ti': blox_qty(2, 'h'),
                'td': blox_qty(0, 's'),
                'p': 0,
                'i': 0,
                'd': 0,
                'error': delta_temp_qty(0),
                'integral': blox_qty(0, 'degC * hour'),
                'derivative': blox_qty(0, 'degC / minute'),
                'derivativeFilter': 'FILTER_NONE',
                'integralReset': 0,
                'boilPointAdjust': delta_temp_qty(0),
                'boilMinOutput': 0,
                'boilModeActive': False,
                'inputId': blox_link('Setpoint', 'SetpointSensorPair'),
                'outputId': blox_link('Cool PWM', 'ActuatorPwm'),
                'drivenOutputId': blox_link('Cool PWM', 'ActuatorPwm', True),
            },
        },
        {
            'id': 'Cool PWM',
            'type': 'ActuatorPwm',
            'groups': [0],
            'serviceId': 'test',
            'data': {
                'constrainedBy': {
                    'constraints': [
                        {
                            'limiting': True,
                            'balanced': {
                                'balancerId': blox_link('Balancer', 'Balancer'),
                                'granted': 10,
                                'id': 1,
                            },
                        },
                        {
                            'limiting': False,
                            'max': 100,
                        }
                    ],
                },
                'desiredSetting': 50,
                'setting': 50,
                'value': 50,
                'actuatorId': blox_link('Cool Actuator', 'DigitalActuator'),
                'drivenActuatorId': blox_link(
                    'Cool Actuator',
                    'DigitalActuator',
                    True,
                ),
                'enabled': True,
                'period': blox_qty(10, 's'),
            },
        },
        {
            'id': 'Cool Actuator',
            'type': 'DigitalActuator',
            'groups': [0],
            'serviceId': 'test',
            'data': {
                'channel': 0,
                'constrainedBy': {
                    'constraints': [
                        {
                            'remaining': blox_qty(10, 'min'),
                            'delayedOn': blox_qty(1, 'h'),
                        },
                        {
                            'remaining': blox_qty(0, 'min'),
                            'delayedOff': blox_qty(1, 'h'),
                        }
                    ],
                },
                'desiredState': 'STATE_ACTIVE',
                'state': 'STATE_ACTIVE',
                'hwDevice': blox_link('Spark Pins', 'Spark3Pins', True),
                'invert': False,
            },
        },
        {
            'id': 'Spark Pins',
            'type': 'Spark3Pins',
            'groups': [0],
            'serviceId': 'test',
            'data': {
                'enableIoSupply12V': True,
                'enableIoSupply5V': True,
                'channels': [],
                'soundAlarm': False,
                'voltage12': 12,
                'voltage5': 5,
            },
        },
        {
            'id': 'DisplaySettings',
            'type': 'DisplaySettings',
            'groups': [0],
            'serviceId': 'test',
            'data': {
                'brightness': 0,
                'name': 'Suggestive Sensors',
                'tempUnit': 'TEMP_CELSIUS',
                'timeZone': 'UTC0',
                'widgets': [
                    {
                        'color': '4169e1',
                        'name': 'Sensor 1',
                        'pos': 1,
                        'tempSensor': blox_link('TempSensorOneWire-1', 'TempSensorInterface'),
                    }
                ]
            }
        }
    ]


def test_calculate_relations():
    blocks = make_blocks()
    result = block_analysis.calculate_relations(blocks)
    result = sorted(result, key=lambda v: v['source'] + ' ' + v['target'])
    assert result == [
        {'source': 'Cool Actuator', 'target': 'Spark Pins', 'relation': ['hwDevice']},
        {'source': 'Cool PID', 'target': 'Cool PWM', 'relation': ['outputId']},
        {
            'source': 'Cool PWM',
            'target': 'Balancer',
            'relation': [
                'constrainedBy',
                'constraints',
                '0',
                'balanced',
                'balancerId',
            ],
        },
        {'source': 'Cool PWM', 'target': 'Cool Actuator', 'relation': ['actuatorId']},
        {'source': 'Heat Actuator', 'target': 'Spark Pins', 'relation': ['hwDevice']},
        {'source': 'Heat PID', 'target': 'Heat PWM', 'relation': ['outputId']},
        {'source': 'Heat PWM', 'target': 'Heat Actuator', 'relation': ['actuatorId']},
        {'source': 'Sensor', 'target': 'Setpoint', 'relation': ['sensorId']},
        {'source': 'Setpoint', 'target': 'Cool PID', 'relation': ['inputId']},
        {'source': 'Setpoint', 'target': 'Heat PID', 'relation': ['inputId']},
    ]


def test_calculate_drive_chains():
    blocks = make_blocks()
    result = block_analysis.calculate_drive_chains(blocks)
    result = sorted(result, key=lambda v: v['target'] + ' ' + v['source'])
    assert result == [
        {'target': 'Cool Actuator', 'source': 'Cool PID', 'intermediate': ['Cool PWM']},
        {'target': 'Cool PWM', 'source': 'Cool PID', 'intermediate': []},
        {'target': 'Heat Actuator', 'source': 'Heat PID', 'intermediate': ['Heat PWM']},
        {'target': 'Heat PWM', 'source': 'Heat PID', 'intermediate': []},
        {'target': 'Spark Pins', 'source': 'Cool PID', 'intermediate': ['Cool Actuator', 'Cool PWM']},
        {'target': 'Spark Pins', 'source': 'Heat PID', 'intermediate': ['Heat Actuator', 'Heat PWM']},
    ]


def test_calculate_circular_drive_chains():
    blocks = [
        {
            'id': 'block-1',
            'type': 'test',
            'data': {
                'ptr1': blox_link('block-2', 'test', True)
            }
        },
        {
            'id': 'block-2',
            'type': 'test',
            'data': {
                'ptr2': blox_link('block-3', 'test', True)
            }
        },
        {
            'id': 'block-3',
            'type': 'test',
            'data': {
                'ptr3': blox_link('block-1', 'test', True)
            }
        },
    ]
    result = block_analysis.calculate_drive_chains(blocks)
    result = sorted(result, key=lambda v: v['target'])
    assert result == [
        {'target': 'block-1', 'source': 'block-1', 'intermediate': ['block-3', 'block-2']},
        {'target': 'block-2', 'source': 'block-2', 'intermediate': ['block-1', 'block-3']},
        {'target': 'block-3', 'source': 'block-3', 'intermediate': ['block-2', 'block-1']},
    ]
