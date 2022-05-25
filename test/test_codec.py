"""
Tests brewblox codec
"""

from unittest.mock import ANY

import pytest
from brewblox_service import features, scheduler

from brewblox_devcon_spark import (codec, connection_sim, exceptions,
                                   service_status, service_store)
from brewblox_devcon_spark.codec import (Codec, DecodeOpts, MetadataOpt,
                                         ProtoEnumOpt)


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


async def test_encode_system_objects(app, client, cdc: Codec):
    objects = [
        {
            'type': 'SysInfo',
            'data': {},
        },
        {
            'type': 'Ticks',
            'data': {},
        },
        {
            'type': 'OneWireBus',
            'data': {},
        },
    ]

    encoded = [await cdc.encode((o['type'], None), o['data']) for o in objects]
    assert encoded


async def test_encode_errors(app, client, cdc: Codec):
    with pytest.raises(TypeError):
        await cdc.encode(('TempSensorOneWire', None), opts={})

    with pytest.raises(exceptions.EncodeException):
        await cdc.encode(('MAGIC', None), {})

    with pytest.raises(exceptions.EncodeException):
        await cdc.encode(('TempSensorOneWire', None), {'Galileo': 'thunderbolts and lightning'})

    with pytest.raises(TypeError):
        await cdc.encode(('TempSensorOneWire', None), 'very very frightening me')


async def test_decode_errors(app, client, cdc: Codec):
    with pytest.raises(TypeError):
        await cdc.decode(('TempSensorOneWire', None), 123)

    identifier, _ = await cdc.encode(('TempSensorOneWire', None), None)
    assert await cdc.decode(identifier, b'Galileo, Figaro - magnificoo') \
        == (('ErrorObject', None), {'error': ANY, 'identifier': ('TempSensorOneWire', None)})

    assert await cdc.decode((1e6, 0), b'\x00') == (('ErrorObject', None), {'error': ANY, 'identifier': (1e6, 0)})
    assert await cdc.decode((1e6, 0), None) == (('UnknownType', None), None)

    with pytest.raises(TypeError):
        await cdc.decode((1e6, 0), b'\x00', {})


async def test_invalid_object(app, client, cdc: Codec):
    assert await cdc.encode(('Invalid', None), {'args': True}) == ((0, 0), 'AA==')
    assert await cdc.decode((0, 0), 'AA==') == (('Invalid', None), {})


async def test_deprecated_object(app, client, cdc: Codec):
    assert await cdc.encode(('DeprecatedObject', None), {'actualId': 100}) == ((65533, 0), 'ZAA=')
    assert await cdc.decode((65533, 0), 'ZAA=') == (('DeprecatedObject', None), {'actualId': 100})


async def test_encode_constraint(app, client, cdc: Codec):
    assert await cdc.decode(('ActuatorPwm', None), b'\x00')
    assert await cdc.encode(('ActuatorPwm', None), {
        'constrainedBy': {
            'constraints': [
                {'min': -100},
                {'max': 100},
            ],
        },
    })


async def test_encode_delta_sec(app, client, cdc: Codec):
    # Check whether [delta_temperature / time] can be converted
    enc_id, enc_val = await cdc.encode(('EdgeCase', None), {
        'deltaV': 100,
    })
    _, dec_val = await cdc.decode(enc_id, enc_val, DecodeOpts(metadata=MetadataOpt.POSTFIX))
    assert dec_val['deltaV[delta_degC / second]'] == pytest.approx(100, 0.1)


async def test_encode_submessage(app, client, cdc: Codec):
    enc_id, enc_val = await cdc.encode(('EdgeCase', 'SubCase'), {})
    assert enc_id == (9001, 1)
    dec_id, dec_val = await cdc.decode(enc_id, enc_val)
    assert dec_id == ('EdgeCase', 'SubCase')


async def test_implements(app, client, cdc: Codec):
    assert await cdc.implements(('EdgeCase', None)) == []
    assert await cdc.implements(('ActuatorPwm', None)) == [
        'ProcessValueInterface',
        'ActuatorAnalogInterface',
        'EnablerInterface',
    ]
    assert await cdc.implements(('ActuatorAnalogInterface', None)) == []


async def test_transcode_interfaces(app, client, cdc: Codec):
    for type in [
        'EdgeCase',
        'BalancerInterface',
        'SetpointSensorPair',
        'SetpointSensorPairInterface',
    ]:
        dec_id = (type, None)
        enc_id, _ = await cdc.encode(dec_id, None)
        dec_id, _ = await cdc.decode(enc_id, None)
        assert dec_id == (type, None)


async def test_stripped_fields(app, client, cdc: Codec, sim_cdc: Codec):
    enc_id, enc_val = await sim_cdc.encode(('EdgeCase', None), {
        'deltaV': 100,  # tag 6
        'logged': 10,  # tag 7
        'strippedFields': [6],
    })
    dec_id, dec_val = await cdc.decode(enc_id, enc_val)
    assert dec_val['deltaV']['value'] is None
    assert dec_val['deltaV']['unit'] == 'delta_degC / second'
    assert dec_val['logged'] == 10
    assert 'strippedFields' not in dec_val.keys()

    _, dec_val = await cdc.decode(enc_id, enc_val,
                                  DecodeOpts(metadata=MetadataOpt.POSTFIX))
    assert dec_val['deltaV[delta_degC / second]'] is None


async def test_driven_fields(app, client, cdc: Codec):
    enc_id, enc_val = await cdc.encode(('EdgeCase', None), {
        'drivenDevice': 10,
        'state': {
            'value[degC]': 10
        }
    })
    dec_id, dec_val = await cdc.decode(enc_id, enc_val)
    assert dec_val['drivenDevice']['id'] == 10
    assert dec_val['drivenDevice']['driven'] is True
    assert dec_val['drivenDevice']['type'] == 'DS2413'


async def test_postfixed_decoding(app, client, cdc: Codec):
    enc_id, enc_val = await cdc.encode(('EdgeCase', None), {
        'drivenDevice': 10,
        'state': {
            'value[degC]': 10
        }
    })

    dec_id, dec_val = await cdc.decode(enc_id, enc_val, DecodeOpts(metadata=MetadataOpt.POSTFIX))
    assert dec_val['drivenDevice<DS2413,driven>'] == 10
    assert dec_val['state']['value[degC]'] == pytest.approx(10, 0.01)


async def test_point_presence(app, client, cdc: Codec):
    enc_id_present, enc_val_present = await cdc.encode(('SetpointProfile', None), {
        'points': [
            {'time': 0, 'temperature[degC]': 0},
            {'time': 10, 'temperature[degC]': 10},
        ]
    })

    enc_id_absent, enc_val_absent = await cdc.encode(('SetpointProfile', None), {
        'points': [
            {'time': 10, 'temperature[degC]': 10},
        ]
    })

    assert enc_val_present != enc_val_absent

    dec_id_present, dec_val_present = await cdc.decode(enc_id_present, enc_val_present)
    dec_id_absent, dec_val_absent = await cdc.decode(enc_id_absent, enc_val_absent)

    assert dec_val_present['points'][0]['time'] == 0


async def test_enum_decoding(app, client, cdc: Codec):
    enc_id, enc_val = await cdc.encode(('DigitalActuator', None), {
        'desiredState': 'STATE_ACTIVE',
    })
    dec_id, dec_val = await cdc.decode(enc_id, enc_val)
    assert dec_val['desiredState'] == 'STATE_ACTIVE'

    # Both strings and ints are valid input
    enc_id_alt, enc_val_alt = await cdc.encode(('DigitalActuator', None), {
        'desiredState': 1,
    })
    assert enc_val_alt == enc_val

    dec_id, dec_val = await cdc.decode(enc_id, enc_val, DecodeOpts(enums=ProtoEnumOpt.INT))
    assert dec_val['desiredState'] == 1
