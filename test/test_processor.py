"""
Tests brewblox_devcon_spark.codec.processor
"""

import pytest

from brewblox_devcon_spark.codec import (DecodeOpts, ProtobufProcessor,
                                         unit_conversion)
from brewblox_devcon_spark.codec.pb2 import TempSensorOneWire_pb2


@pytest.fixture
def degf_processor(app):
    c = unit_conversion.UnitConverter(app)
    c.temperature = 'degF'
    m = ProtobufProcessor(c, strip_readonly=False)
    return m


@pytest.fixture
def degc_processor(app):
    c = unit_conversion.UnitConverter(app)
    c.temperature = 'degC'
    return ProtobufProcessor(c)


@pytest.fixture
def desc():
    return TempSensorOneWire_pb2.Block.DESCRIPTOR


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


def test_pre_encode_fields(degf_processor, desc):
    vals = generate_encoding_data()
    degf_processor.pre_encode(desc, vals)

    # converted to (delta) degC
    # scaled * 256
    # rounded to int
    assert vals == generate_decoding_data()


def test_post_decode_fields(degf_processor, desc):
    vals = generate_decoding_data()
    degf_processor.post_decode(desc, vals, DecodeOpts())
    assert vals['offset']['value'] == pytest.approx(20, 0.1)
    assert vals['value']['value'] == pytest.approx(100, 0.1)


def test_decode_no_system(degc_processor, desc):
    vals = generate_decoding_data()
    degc_processor.post_decode(desc, vals, DecodeOpts())
    assert vals['offset']['value'] > 0
    assert vals['value']['value'] > 0


def test_pack_bit_flags(degf_processor):
    assert degf_processor.pack_bit_flags([0, 2, 1]) == 7

    with pytest.raises(ValueError):
        degf_processor.pack_bit_flags([8])


def test_unpack_bit_flags(degf_processor):
    assert degf_processor.unpack_bit_flags(7) == [0, 1, 2]
    assert degf_processor.unpack_bit_flags(255) == [i for i in range(8)]


def test_null_values(degf_processor, desc):
    vals = generate_encoding_data()
    vals['offset[delta_degF]'] = None
    vals['address'] = None

    degf_processor.pre_encode(desc, vals)
    assert 'address' not in vals


def test_get_obj_tags(degf_processor, desc):
    vals = generate_encoding_data()
    degf_processor.pre_encode(desc, vals)
    assert sorted(degf_processor.obj_tags(desc, vals)) == [
        1,  # value
        3,  # offset
        4,  # address
    ]
