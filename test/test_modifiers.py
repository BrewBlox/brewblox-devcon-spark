"""
Tests brewblox_codec_spark.modifiers
"""

from brewblox_codec_spark import _path_extension  # isort:skip

import pytest

import OneWireTempSensor_pb2
from brewblox_codec_spark import modifiers

_path_extension.avoid_lint_errors()


@pytest.fixture(scope='module')
def mod():
    return modifiers.Modifier('config/fahrenheit_system.txt')


def generate_encoding_data():
    return {
        'settings': {
            'address': 'address',
            'offset[delta_degF]': 20
        },
        'state': {
            'value[degF]': 10
        }
    }


def generate_decoding_data():
    return {
        'settings': {
            'address': 'address',
            'offset': 2844
        },
        'state': {
            'value': -3129
        }
    }


def test_modify_if_present(mod):
    input = generate_encoding_data()
    output = mod.modify_if_present(input, 'settings/address', lambda s: s[::-1])

    assert output['settings']['address'] == 'sserdda'
    assert id(input) == id(output)
    assert input != generate_encoding_data()


def test_encode_options(mod):
    vals = generate_encoding_data()
    mod.encode_options(OneWireTempSensor_pb2.OneWireTempSensor(), vals)

    # converted to delta_degC
    # scaled * 256
    # rounded to int
    assert vals == generate_decoding_data()


def test_decode_options(mod):
    vals = {
        'settings': {
            'address': 'address',
            'offset': 2844
        },
        'state': {
            'value': -3129
        }
    }

    mod.decode_options(OneWireTempSensor_pb2.OneWireTempSensor(), vals)
    print(vals)
    assert vals['settings']['offset[delta_degF]'] == pytest.approx(20, 0.1)
    assert vals['state']['value[degF]'] == pytest.approx(10, 0.1)
