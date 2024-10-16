"""
Imports all auto-generated pb_2.py files
"""

import sys
from pathlib import Path

# Proto files must be imported as an absolute path
# For this to happen without polluting the repo root directory, we have to extend sys.path
# The import is done inside the if statement to avoid autopep8 / isort interfering
if 'brewblox_pb2' not in sys.modules:  # pragma: no cover
    sys.path.append(f'{Path(__file__).parent.resolve()}/proto-compiled/')

    import ActuatorAnalogMock_pb2
    import ActuatorLogic_pb2
    import ActuatorOffset_pb2
    import ActuatorPwm_pb2
    import AnalogGpioModule_pb2
    import Balancer_pb2
    import brewblox_pb2
    import command_pb2
    import DigitalActuator_pb2
    import DigitalInput_pb2
    import DisplaySettings_pb2
    import DS2408_pb2
    import DS2413_pb2
    import EdgeCase_pb2
    import FastPwm_pb2
    import GpioModule_pb2
    import MockPins_pb2
    import MotorValve_pb2
    import Mutex_pb2
    import Pid_pb2
    import Screen_pb2
    import Sequence_pb2
    import SetpointProfile_pb2
    import SetpointSensorPair_pb2
    import Spark2Pins_pb2
    import Spark3Pins_pb2
    import SysInfo_pb2
    import TempSensorAnalog_pb2
    import TempSensorCombi_pb2
    import TempSensorExternal_pb2
    import TempSensorMock_pb2
    import TempSensorOneWire_pb2
    import Variables_pb2
    import WiFiSettings_pb2

__all__ = [
    'ActuatorAnalogMock_pb2',
    'ActuatorLogic_pb2',
    'ActuatorOffset_pb2',
    'ActuatorPwm_pb2',
    'AnalogGpioModule_pb2',
    'Balancer_pb2',
    'brewblox_pb2',
    'command_pb2',
    'DigitalActuator_pb2',
    'DigitalInput_pb2',
    'DisplaySettings_pb2',
    'DS2408_pb2',
    'DS2413_pb2',
    'EdgeCase_pb2',
    'FastPwm_pb2',
    'GpioModule_pb2',
    'MockPins_pb2',
    'MotorValve_pb2',
    'Mutex_pb2',
    'Pid_pb2',
    'Screen_pb2',
    'Sequence_pb2',
    'SetpointProfile_pb2',
    'SetpointSensorPair_pb2',
    'Spark2Pins_pb2',
    'Spark3Pins_pb2',
    'SysInfo_pb2',
    'TempSensorAnalog_pb2',
    'TempSensorCombi_pb2',
    'TempSensorExternal_pb2',
    'TempSensorMock_pb2',
    'TempSensorOneWire_pb2',
    'Variables_pb2',
    'WiFiSettings_pb2',
]
