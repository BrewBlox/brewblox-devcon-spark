"""
Tests brewblox_devcon_spark.codec.modifiers
"""

import pytest

from brewblox_devcon_spark.codec import CodecOpts, modifiers, unit_conversion
from brewblox_devcon_spark.codec.pb2 import TempSensorOneWire_pb2


@pytest.fixture
def f_mod(app):
    c = unit_conversion.UnitConverter(app)
    c.temperature = 'degF'
    m = modifiers.Modifier(c, strip_readonly=False)
    return m


@pytest.fixture
def c_mod(app):
    c = unit_conversion.UnitConverter(app)
    c.temperature = 'degC'
    return modifiers.Modifier(c)


def generate_encoding_data():
    return {
        'value[degF]': 100,
        'offset[delta_degF]': 20,
        'address': 'aabbccdd',
    }


def generate_decoding_data():
    return {
        'value': 154738,
        'offset': 45511,
        'address': 3721182122,
    }


def test_encode_options(f_mod):
    vals = generate_encoding_data()
    f_mod.encode_options(TempSensorOneWire_pb2.TempSensorOneWire(), vals, CodecOpts())

    # converted to (delta) degC
    # scaled * 256
    # rounded to int
    assert vals == generate_decoding_data()


def test_decode_options(f_mod):
    vals = generate_decoding_data()
    f_mod.decode_options(TempSensorOneWire_pb2.TempSensorOneWire(), vals, CodecOpts())
    assert vals['offset']['value'] == pytest.approx(20, 0.1)
    assert vals['value']['value'] == pytest.approx(100, 0.1)


def test_decode_no_system(c_mod):
    vals = generate_decoding_data()
    c_mod.decode_options(TempSensorOneWire_pb2.TempSensorOneWire(), vals, CodecOpts())
    assert vals['offset']['value'] > 0
    assert vals['value']['value'] > 0


def test_pack_bit_flags(f_mod):
    assert f_mod.pack_bit_flags([0, 2, 1]) == 7

    with pytest.raises(ValueError):
        f_mod.pack_bit_flags([8])


def test_unpack_bit_flags(f_mod):
    assert f_mod.unpack_bit_flags(7) == [0, 1, 2]
    assert f_mod.unpack_bit_flags(255) == [i for i in range(8)]


def test_null_values(f_mod):
    vals = generate_encoding_data()
    vals['offset[delta_degF]'] = None
    vals['address'] = None

    f_mod.encode_options(TempSensorOneWire_pb2.TempSensorOneWire(), vals, CodecOpts())
    assert 'address' not in vals
