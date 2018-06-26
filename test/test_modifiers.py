"""
Tests brewblox_codec_spark.modifiers
"""

import pytest
from brewblox_codec_spark import modifiers
from brewblox_codec_spark.proto import OneWireTempSensor_pb2


@pytest.fixture(scope='module')
def mod():
    return modifiers.Modifier('config/fahrenheit_system.txt')


def encode_temp_sensor_data():
    return {
        'settings': {
            'address': 'address',
            'offset[delta_degF]': 20
        }
    }


def decode_temp_sensor_data():
    return {
        'settings': {
            'address': 'address',
            'offset': 2844
        }
    }


def test_modify_if_present(mod):
    input = encode_temp_sensor_data()
    output = mod.modify_if_present(input, 'settings/address', lambda s: s[::-1])

    assert output['settings']['address'] == 'sserdda'
    assert id(input) == id(output)
    assert input != encode_temp_sensor_data()


def test_encode_quantity(mod):
    vals = encode_temp_sensor_data()
    mod.encode_quantity(OneWireTempSensor_pb2.OneWireTempSensor(), vals)

    # converted to delta_degC
    # scaled * 256
    # rounded to int
    assert vals == decode_temp_sensor_data()


def test_decode_quantity(mod):
    vals = {
        'settings': {
            'address': 'address',
            'offset': 2844
        }
    }

    mod.decode_quantity(OneWireTempSensor_pb2.OneWireTempSensor(), vals)
    print(vals['settings'])
    assert vals['settings']['offset[delta_degF]'] == pytest.approx(20, 0.1)
