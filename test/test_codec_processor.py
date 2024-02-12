import pytest

from brewblox_devcon_spark.codec import (DecodeOpts, ProtobufProcessor,
                                         unit_conversion)
from brewblox_devcon_spark.codec.pb2 import TempSensorOneWire_pb2
from brewblox_devcon_spark.models import DecodedPayload, MaskField, MaskMode


@pytest.fixture
def degf_processor():
    unit_conversion.setup()
    unit_conversion.CV.get().temperature = 'degF'
    return ProtobufProcessor(strip_readonly=False)


@pytest.fixture
def degc_processor():
    unit_conversion.setup()
    unit_conversion.CV.get().temperature = 'degC'
    return ProtobufProcessor()


@pytest.fixture
def desc():
    return TempSensorOneWire_pb2.Block.DESCRIPTOR


def generate_encoding_data() -> DecodedPayload:
    return DecodedPayload(
        blockId=1,
        blockType='TempSensorOneWire',
        content={
            'value[degF]': 100,
            'offset[delta_degF]': 20,
            'address': 'aabbccdd',
        },
    )


def generate_decoding_data() -> DecodedPayload:
    return DecodedPayload(
        blockId=1,
        blockType='TempSensorOneWire',
        content={
            'value': 154738,
            'offset': 45511,
            'address': 3721182122,
        },
    )


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
    assert vals.content['offset']['value'] == pytest.approx(20, 0.1)
    assert vals.content['value']['value'] == pytest.approx(100, 0.1)


def test_decode_no_system(degc_processor, desc):
    vals = generate_decoding_data()
    degc_processor.post_decode(desc, vals, DecodeOpts())
    assert vals.content['offset']['value'] > 0
    assert vals.content['value']['value'] > 0


def test_pack_bit_flags(degf_processor):
    assert degf_processor.pack_bit_flags([0, 2, 1]) == 7

    with pytest.raises(ValueError):
        degf_processor.pack_bit_flags([8])


def test_unpack_bit_flags(degf_processor):
    assert degf_processor.unpack_bit_flags(7) == [0, 1, 2]
    assert degf_processor.unpack_bit_flags(255) == [i for i in range(8)]


def test_null_values(degf_processor, desc):
    vals = generate_encoding_data()
    vals.content['offset[delta_degF]'] = None
    vals.content['address'] = None

    degf_processor.pre_encode(desc, vals)
    assert 'address' not in vals.content


def test_masking(degf_processor, desc):
    vals = generate_encoding_data()
    vals.maskMode = MaskMode.INCLUSIVE
    degf_processor.pre_encode(desc, vals)
    assert sorted(list((f.address for f in vals.maskFields))) == [
        [1],  # value
        [3],  # offset
        [4],  # address
    ]

    vals = generate_decoding_data()
    vals.maskMode = MaskMode.EXCLUSIVE
    vals.maskFields = [MaskField(address=[1])]  # value
    degf_processor.post_decode(desc, vals, DecodeOpts())
    assert vals.content['value']['value'] is None
