"""
Tests brewblox_codec_spark.modifiers
"""

import logging

import pytest
from brewblox_codec_spark import modifiers, path_extension
from brewblox_codec_spark.proto import OneWireTempSensor_pb2

# We import path_extension for its side effects
# "use" the import to avoid pep8 complaints
# Alternative (adding noqa mark), would also prevent IDE suggestions
logging.debug(f'Extending path with {path_extension.PROTO_PATH}')


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


def test_modify_if_present():
    input = encode_temp_sensor_data()
    output = modifiers.modify_if_present(input, 'settings/address', lambda s: s[::-1])

    assert output['settings']['address'] == 'sserdda'
    assert id(input) == id(output)
    assert input != encode_temp_sensor_data()


def test_encode_quantity():
    vals = encode_temp_sensor_data()
    modifiers.encode_quantity(OneWireTempSensor_pb2.OneWireTempSensor(), vals)

    # converted to delta_degC
    # scaled * 256
    # rounded to int
    assert vals == decode_temp_sensor_data()


def test_decode_quantity():
    vals = {
        'settings': {
            'address': 'address',
            'offset': 2844
        }
    }

    modifiers.decode_quantity(OneWireTempSensor_pb2.OneWireTempSensor(), vals)
    print(vals['settings'])
    assert vals['settings']['offset[delta_degC]'] == pytest.approx(2844 / 256, 0.1)
