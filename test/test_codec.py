"""
Tests brewblox codec
"""

import pytest
from brewblox_service import features, scheduler

from brewblox_devcon_spark import (codec, connection_sim, exceptions,
                                   service_status, service_store)
from brewblox_devcon_spark.codec import (Codec, DecodeOpts, MetadataOpt,
                                         ProtoEnumOpt)
from brewblox_devcon_spark.models import (DecodedPayload, EncodedPayload,
                                          MaskMode)

TEMP_SENSOR_TYPE_INT = 302


@pytest.fixture
def app(app):
    service_status.setup(app)
    scheduler.setup(app)
    codec.setup(app)
    service_store.setup(app)
    connection_sim.setup(app)
    return app


@pytest.fixture
def cdc(app) -> Codec:
    return codec.fget(app)


@pytest.fixture
def sim_cdc(app) -> Codec:
    return features.get(app, key='sim_codec')


async def test_type_conversion():
    for (joined, split) in [
        ['Pid', ('Pid', None)],
        ['Pid.subtype', ('Pid', 'subtype')],
        ['Pid.subtype.subsubtype', ('Pid', 'subtype.subsubtype')]
    ]:
        assert codec.split_type(joined) == split
        assert codec.join_type(*split) == joined


async def test_encode_system_objects(app, client, cdc: Codec):
    types = [
        'SysInfo',
        'Ticks',
        'OneWireBus'
    ]

    encoded = [
        cdc.encode_payload(DecodedPayload(
            blockId=1,
            blockType=t,
            content={},
        ))
        for t in types]

    assert encoded


async def test_encode_errors(app, client, cdc: Codec):
    with pytest.raises(exceptions.EncodeException):
        cdc.encode_request({})

    with pytest.raises(exceptions.EncodeException):
        cdc.encode_response({})

    with pytest.raises(exceptions.EncodeException):
        cdc.encode_payload(DecodedPayload(
            blockId=1,
            blockType='MAGIC'
        ))

    with pytest.raises(exceptions.EncodeException):
        cdc.encode_payload(DecodedPayload(
            blockId=1,
            blockType='TempSensorOneWire',
            content={'Galileo': 'thunderbolts and lightning'}
        ))


async def test_decode_errors(app, client, cdc: Codec):
    with pytest.raises(exceptions.DecodeException):
        cdc.decode_request('Is this just fantasy?')

    with pytest.raises(exceptions.DecodeException):
        cdc.decode_response('Caught in a landslide')

    error_object = cdc.decode_payload(EncodedPayload(
        blockId=1,
        blockType=TEMP_SENSOR_TYPE_INT,
        content='Galileo, Figaro - magnificoo',
    ))
    assert error_object.blockType == 'ErrorObject'
    assert error_object.content['error']

    error_object = cdc.decode_payload(EncodedPayload(
        blockId=1,
        blockType=1e6,
    ))
    assert error_object.blockType == 'UnknownType'


async def test_deprecated_object(app, client, cdc: Codec):
    payload = cdc.encode_payload(DecodedPayload(
        blockId=1,
        blockType='DeprecatedObject',
        content={'actualId': 100},
    ))
    assert payload.blockType == 65533
    assert payload.content == 'ZAA='

    payload = cdc.decode_payload(payload)
    assert payload.blockType == 'DeprecatedObject'
    assert payload.content == {'actualId': 100}


async def test_encode_constraint(app, client, cdc: Codec):
    assert cdc.decode_payload(EncodedPayload(
        blockId=1,
        blockType='ActuatorPwm',
        content='\x00',
    ))
    assert cdc.encode_payload(DecodedPayload(
        blockId=1,
        blockType='ActuatorPwm',
        content={
            'constrainedBy': {
                'constraints': [
                    {'min': -100},
                    {'max': 100},
                ],
            },
        },
    ))


async def test_encode_delta_sec(app, client, cdc: Codec):
    # Check whether [delta_temperature / time] can be converted
    payload = cdc.encode_payload(DecodedPayload(
        blockId=1,
        blockType='EdgeCase',
        content={'deltaV': 100}
    ))
    payload = cdc.decode_payload(payload, opts=DecodeOpts(metadata=MetadataOpt.POSTFIX))
    assert payload.content['deltaV[delta_degC / second]'] == pytest.approx(100, 0.1)


async def test_encode_submessage(app, client, cdc: Codec):
    payload = cdc.encode_payload(DecodedPayload(
        blockId=1,
        blockType='EdgeCase',
        subtype='SubCase',
        content={}
    ))
    assert payload.blockType == 9001
    assert payload.subtype == 1

    payload = cdc.decode_payload(payload)
    assert payload.blockType == 'EdgeCase'
    assert payload.subtype == 'SubCase'

    # Interface encoding
    payload = cdc.encode_payload(DecodedPayload(
        blockId=1,
        blockType='EdgeCase',
    ))
    assert payload.blockType == 9001

    payload = cdc.decode_payload(payload)
    assert payload.blockType == 'EdgeCase'


async def test_transcode_interfaces(app, client, cdc: Codec):
    for type in [
        'EdgeCase',
        'BalancerInterface',
        'SetpointSensorPair',
        'SetpointSensorPairInterface',
    ]:
        payload = cdc.encode_payload(DecodedPayload(
            blockId=1,
            blockType=type,
        ))
        payload = cdc.decode_payload(payload)
        assert payload.blockType == type


async def test_exclusive_mask(app, client, cdc: Codec, sim_cdc: Codec):
    enc_payload = sim_cdc.encode_payload(DecodedPayload(
        blockId=1,
        blockType='EdgeCase',
        content={
            'deltaV': 100,  # tag 6
            'logged': 10,  # tag 7
        },
        maskMode=MaskMode.EXCLUSIVE,
        mask=[6],
    ))
    payload = cdc.decode_payload(enc_payload)

    assert payload.content['deltaV']['value'] is None
    assert payload.content['deltaV']['unit'] == 'delta_degC / second'
    assert payload.content['logged'] == 10
    assert payload.maskMode == MaskMode.EXCLUSIVE
    assert payload.mask == [6]

    payload = cdc.decode_payload(enc_payload, opts=DecodeOpts(metadata=MetadataOpt.POSTFIX))
    assert payload.content['deltaV[delta_degC / second]'] is None


async def test_driven_fields(app, client, cdc: Codec):
    payload = cdc.encode_payload(DecodedPayload(
        blockId=1,
        blockType='EdgeCase',
        content={
            'drivenDevice': 10,
            'state': {
                'value[degC]': 10
            }
        },
    ))
    payload = cdc.decode_payload(payload)
    assert payload.content['drivenDevice']['id'] == 10
    assert payload.content['drivenDevice']['driven'] is True
    assert payload.content['drivenDevice']['type'] == 'DS2413'


async def test_postfixed_decoding(app, client, cdc: Codec):
    payload = cdc.encode_payload(DecodedPayload(
        blockId=1,
        blockType='EdgeCase',
        content={
            'drivenDevice': 10,
            'state': {
                'value[degC]': 10
            }
        },
    ))
    payload = cdc.decode_payload(payload, opts=DecodeOpts(metadata=MetadataOpt.POSTFIX))
    assert payload.content['drivenDevice<DS2413,driven>'] == 10
    assert payload.content['state']['value[degC]'] == pytest.approx(10, 0.01)


async def test_point_presence(app, client, cdc: Codec):
    present_payload = cdc.encode_payload(DecodedPayload(
        blockId=1,
        blockType='SetpointProfile',
        content={
            'points': [
                {'time': 0, 'temperature[degC]': 0},
                {'time': 10, 'temperature[degC]': 10},
            ]
        },
    ))

    absent_payload = cdc.encode_payload(DecodedPayload(
        blockId=1,
        blockType='SetpointProfile',
        content={
            'points': [
                {'time': 10, 'temperature[degC]': 10},
            ]
        },
    ))

    assert present_payload.content != absent_payload.content

    present_payload = cdc.decode_payload(present_payload)
    absent_payload = cdc.decode_payload(absent_payload)
    assert present_payload.content['points'][0]['time'] == 0


async def test_enum_decoding(app, client, cdc: Codec):
    encoded_payload = cdc.encode_payload(DecodedPayload(
        blockId=1,
        blockType='DigitalActuator',
        content={
            'desiredState': 'STATE_ACTIVE',
        },
    ))

    encoded_int_payload = cdc.encode_payload(DecodedPayload(
        blockId=1,
        blockType='DigitalActuator',
        content={
            'desiredState': 1,
        },
    ))

    # String and int enums are both valid input
    assert encoded_payload.content == encoded_int_payload.content

    payload = cdc.decode_payload(encoded_payload)
    assert payload.content['desiredState'] == 'STATE_ACTIVE'

    payload = cdc.decode_payload(encoded_payload, opts=DecodeOpts(enums=ProtoEnumOpt.INT))
    assert payload.content['desiredState'] == 1
