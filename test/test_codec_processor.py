import random
import sys

import pytest
from google.protobuf import json_format
from google.protobuf.descriptor import Descriptor, FieldDescriptor

from brewblox_devcon_spark import exceptions
from brewblox_devcon_spark.codec import ProtobufProcessor, descriptors, processor, unit_conversion
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
    # None, and typed objects without value, reset a writable field to its default.
    # A readonly field (only encoded without filtering) is left out: None is invalid.
    vals = generate_encoding_data()
    vals.content['offset[delta_degF]'] = None
    vals.content['address'] = None
    vals.content['value[degF]'] = {'__bloxtype': 'Quantity', 'unit': 'degC', 'value': None}
    vals.content['oneWireBusId'] = {'__bloxtype': 'Link', 'type': 'OneWireBusInterface', 'id': None}

    degf_processor.pre_encode(desc, vals, filter_values=False)
    assert vals.content == {'offset': 0, 'address': 0, 'oneWireBusId': 0}

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


def _scaled_fields() -> list[FieldDescriptor]:
    """One field for every combination of scale, unit and integer type in the compiled protos"""
    found: dict[tuple, FieldDescriptor] = {}

    def walk(desc: Descriptor):
        for field in desc.fields:
            opts = descriptors.options(field)
            if opts.scale:
                found.setdefault((opts.scale, opts.unit, field.cpp_type), field)
        for nested in desc.nested_types:
            walk(nested)

    for module in list(sys.modules.values()):
        if module.__name__.endswith('_pb2') and hasattr(module, 'DESCRIPTOR'):
            for desc in module.DESCRIPTOR.message_types_by_name.values():
                walk(desc)
    return list(found.values())


def test_decimals():
    # degC and all other units: the scale alone decides
    assert [processor._decimals(scale, 1) for scale in [2, 256, 1000, 4096, 16384, 2**19]] == [1, 3, 3, 4, 5, 6]
    # degF: a step is 1.8 times larger
    assert [processor._decimals(scale, 1.8) for scale in [2, 256, 1000, 4096, 16384]] == [1, 3, 3, 4, 4]
    # Too fine for a float to hold more digits: not rounded
    assert processor._decimals(2**41, 1) is None


@pytest.mark.parametrize('temperature', ['degC', 'degF'])
@pytest.mark.parametrize('field', _scaled_fields(), ids=lambda f: f.full_name)
def test_rounding_is_lossless(temperature: str, field: FieldDescriptor):
    """Decoded values are rounded to the decimals of their scale, and encode back to the same integer"""
    unit_conversion.setup()
    unit_conversion.CV.get().temperature = temperature
    proc = ProtobufProcessor()
    desc = field.containing_type
    opts = descriptors.options(field)
    unsigned = field.cpp_type in (FieldDescriptor.CPPTYPE_UINT32, FieldDescriptor.CPPTYPE_UINT64)
    low = 0 if unsigned else -(2**31)

    factor = proc._converter.to_user_factor(proc.unit_name(opts.unit)) if opts.unit else 1
    decimals = processor._decimals(opts.scale, factor)

    rng = random.Random(field.full_name)
    numbers = [*range(0 if unsigned else -500, 500), *(rng.randint(low, 2**31 - 1) for _ in range(500))]
    if opts.null_if_zero or opts.omit_if_zero:
        numbers = [n for n in numbers if n != 0]

    for n in numbers:
        message = desc._concrete_class()
        if field.is_repeated:
            getattr(message, field.name).append(n)
        else:
            setattr(message, field.name, n)
        content = json_format.MessageToDict(
            message, preserving_proto_field_name=True, always_print_fields_with_no_presence=True
        )
        decoded = proc.post_decode(desc, DecodedPayload(blockId=1, blockType='Test', content=content))

        value = decoded.content[field.name]
        number = value[0] if field.is_repeated else value
        number = number['value'] if isinstance(number, dict) else number
        if decimals is not None:
            assert number == round(number, decimals)

        encoded = DecodedPayload(blockId=1, blockType='Test', content={field.name: value})
        proc.pre_encode(desc, encoded, filter_values=False)
        result = encoded.content[field.name]
        assert int(result[0] if field.is_repeated else result) == n, (n, value)
