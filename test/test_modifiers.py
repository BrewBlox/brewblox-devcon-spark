"""
Tests brewblox_devcon_spark.codec.modifiers
"""

from brewblox_devcon_spark.codec import _path_extension  # isort:skip

import pytest

import OneWireTempSensor_pb2
from brewblox_devcon_spark.codec import modifiers

_path_extension.avoid_lint_errors()


@pytest.fixture(scope='module')
def mod():
    return modifiers.Modifier('config/fahrenheit_system.txt')


@pytest.fixture(scope='module')
def k_mod():
    return modifiers.Modifier(None)


def generate_encoding_data():
    return {
        'settings': {
            'address': 'aabbccdd',
            'offset[delta_degF]': 20
        },
        'state': {
            'value[degF]': 10
        }
    }


def generate_decoding_data():
    return {
        'settings': {
            'address': 'qrvM3Q==',
            'offset': 2844
        },
        'state': {
            'value': -3129
        }
    }


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
            'address': 'qrvM3Q==',
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


def test_decode_no_system(k_mod):
    vals = {
        'settings': {
            'address': 'qrvM3Q==',
            'offset': 2844
        },
        'state': {
            'value': -3129
        }
    }

    k_mod.decode_options(OneWireTempSensor_pb2.OneWireTempSensor(), vals)
    print(vals)
    assert vals['settings']['offset[kelvin]'] > 0
    assert vals['state']['value[kelvin]'] > 0
