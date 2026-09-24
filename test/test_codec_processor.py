import pytest

from brewblox_devcon_spark import exceptions
from brewblox_devcon_spark.codec import ProtobufProcessor, unit_conversion
from brewblox_devcon_spark.codec.pb2 import TempSensorOneWire_pb2
from brewblox_devcon_spark.models import DecodedPayload, ReadMode


@pytest.fixture
def degf_processor():
    unit_conversion.setup()
    unit_conversion.CV.get().temperature = 'degF'
    return ProtobufProcessor()


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


def test_pre_encode_fields(degf_processor: ProtobufProcessor, desc):
    vals = generate_encoding_data()
    degf_processor.pre_encode(desc, vals, filter_values=False)

    # converted to (delta) degC
    # scaled * 256
    # rounded to int
    assert vals == generate_decoding_data()


def test_post_decode_fields(degf_processor: ProtobufProcessor, desc):
    vals = generate_decoding_data()
    degf_processor.post_decode(desc, vals, filter_values=False)
    assert vals.content['offset']['value'] == pytest.approx(20, 0.1)
    assert vals.content['value']['value'] == pytest.approx(100, 0.1)


def test_decode_no_system(degc_processor: ProtobufProcessor, desc):
    vals = generate_decoding_data()
    degc_processor.post_decode(desc, vals)
    assert vals.content['offset']['value'] > 0
    assert vals.content['value']['value'] > 0


def test_pack_bit_flags(degf_processor: ProtobufProcessor):
    assert degf_processor.pack_bit_flags([0, 2, 1]) == 7

    with pytest.raises(ValueError):
        degf_processor.pack_bit_flags([8])


def test_unpack_bit_flags(degf_processor: ProtobufProcessor):
    assert degf_processor.unpack_bit_flags(7) == [0, 1, 2]
    assert degf_processor.unpack_bit_flags(255) == [i for i in range(8)]


def test_null_values(degf_processor: ProtobufProcessor, desc):
    # None, and typed objects without value, are absent: the controller keeps its value
    vals = generate_encoding_data()
    vals.content['offset[delta_degF]'] = None
    vals.content['address'] = None
    vals.content['value[degF]'] = {'__bloxtype': 'Quantity', 'unit': 'degC', 'value': None}
    vals.content['oneWireBusId'] = {'__bloxtype': 'Link', 'type': 'OneWireBusInterface', 'id': None}

    degf_processor.pre_encode(desc, vals, filter_values=False)
    assert vals.content == {}

    # Absent keys are not added
    vals = DecodedPayload(blockId=1, blockType='TempSensorOneWire', content={'offset[delta_degC]': 0})
    degf_processor.pre_encode(desc, vals)
    assert vals.content == {'offset': 0}


def test_invalid_values(degf_processor: ProtobufProcessor, desc):
    # None is the invalid marker. Quantities and links keep their typed object.
    vals = DecodedPayload(
        blockId=1,
        blockType='TempSensorOneWire',
        content={'value': None, 'address': None, 'oneWireBusId': None},
    )
    degf_processor.post_decode(desc, vals)
    assert vals.content == {
        'value': {'__bloxtype': 'Quantity', 'unit': 'degF', 'value': None, 'readonly': True},
        'address': None,
        'oneWireBusId': {'__bloxtype': 'Link', 'type': 'OneWireBusInterface', 'id': None},
    }


def test_fill(degf_processor: ProtobufProcessor, desc):
    # Absent optional fields: readonly is invalid (None), writable gets its default
    assert degf_processor.fill(desc, {}) == {'value': None, 'offset': 0, 'address': '0', 'oneWireBusId': 0}
    assert degf_processor.fill(desc, {}, ReadMode.STORED) == {
        'value': None,
        'offset': 0,
        'address': '0',
        'oneWireBusId': 0,
    }
    # CHANGED: absent writable fields are unchanged
    assert degf_processor.fill(desc, {}, ReadMode.CHANGED) == {'value': None}
    assert degf_processor.fill(desc, {'value': 10}, ReadMode.CHANGED) == {'value': 10}


def test_pre_encode_names_failing_field(degc_processor: ProtobufProcessor, desc):
    """
    A conversion error names the field and the offending value.
    Without it, the caller only sees a bare TypeError from int(round(value)).
    """
    payload = DecodedPayload(
        blockId=1,
        blockType='TempSensorOneWire',
        content={'oneWireBusId': 'not-a-nid'},
    )

    with pytest.raises(exceptions.EncodeException) as info:
        degc_processor.pre_encode(desc, payload)

    assert 'oneWireBusId' in str(info.value)
    assert 'not-a-nid' in str(info.value)


def test_post_decode_names_failing_field(degc_processor: ProtobufProcessor, desc):
    """
    Decoding never raises to the caller - the error is folded into an
    ErrorObject stub - so the message is the only diagnostic available.
    """
    payload = DecodedPayload(
        blockId=1,
        blockType='TempSensorOneWire',
        # hexed conversion packs into 8 unsigned bytes, and overflows here
        content={'address': -1},
    )

    with pytest.raises(exceptions.DecodeException) as info:
        degc_processor.post_decode(desc, payload)

    assert 'address' in str(info.value)
