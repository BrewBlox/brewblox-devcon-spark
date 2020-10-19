"""
Tests brewblox codec
"""

import pytest
from brewblox_service import features, scheduler
from mock import ANY

from brewblox_devcon_spark import (codec, commander_sim, config_store,
                                   exceptions, service_status)
from brewblox_devcon_spark.codec import (Codec, CodecOpts, MetadataOpt,
                                         ProtoEnumOpt)


@pytest.fixture
def app(app):
    service_status.setup(app)
    scheduler.setup(app)
    config_store.setup(app)
    commander_sim.setup(app)
    codec.setup(app)
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
        {
            'type': 'Groups',
            'data': {
                'active': [0]
            },
        }
    ]

    encoded = [await cdc.encode(o['type'], o['data']) for o in objects]
    assert encoded


async def test_encode_errors(app, client, cdc: Codec):
    with pytest.raises(TypeError):
        await cdc.encode('TempSensorOneWire', None)

    with pytest.raises(TypeError):
        await cdc.encode('TempSensorOneWire', opts={})

    with pytest.raises(exceptions.EncodeException):
        await cdc.encode('MAGIC', {})

    with pytest.raises(exceptions.EncodeException):
        await cdc.encode('TempSensorOneWire', {'Galileo': 'thunderbolts and lightning'})


async def test_decode_errors(app, client, cdc: Codec):
    with pytest.raises(TypeError):
        await cdc.decode('TempSensorOneWire', 'string')

    type_int = await cdc.encode('TempSensorOneWire')
    assert await cdc.decode(type_int, b'very very frightening me') \
        == ('ErrorObject', {'error': ANY, 'type': 'TempSensorOneWire'})

    assert await cdc.decode(1e6, b'\x00') == ('ErrorObject', {'error': ANY, 'type': 1e6})
    assert await cdc.decode(1e6) == 'UnknownType'

    with pytest.raises(TypeError):
        await cdc.decode(1e6, b'\x00', {})


async def test_invalid_object(app, client, cdc: Codec):
    assert await cdc.encode('Invalid', {'args': True}) == (0, b'\x00')
    assert await cdc.decode(0, b'\xAA') == ('Invalid', {})


async def test_deprecated_object(app, client, cdc: Codec):
    assert await cdc.encode('DeprecatedObject', {'actualId': 100}) == (65533, b'\x64\x00')
    assert await cdc.decode(65533, b'\x64\x00') == ('DeprecatedObject', {'actualId': 100})


async def test_encode_constraint(app, client, cdc: Codec):
    assert await cdc.decode('ActuatorPwm', b'\x00')
    assert await cdc.encode('ActuatorPwm', {
        'constrainedBy': {
            'constraints': [
                {'min': -100},
                {'max': 100},
            ],
        },
    })


async def test_encode_delta_sec(app, client, cdc: Codec):
    # Check whether [delta_temperature / time] can be converted
    enc_id, enc_val = await cdc.encode('EdgeCase', {
        'deltaV': 100,
    })
    dec_id, dec_val = await cdc.decode(enc_id, enc_val, CodecOpts(metadata=MetadataOpt.POSTFIX))
    assert dec_val['deltaV[delta_degC / second]'] == pytest.approx(100, 0.1)


async def test_transcode_interfaces(app, client, cdc: Codec):
    types = [
        'EdgeCase',
        'BalancerInterface',
        'SetpointSensorPair',
        'SetpointSensorPairInterface'
    ]
    assert [await cdc.decode(await cdc.encode(t)) for t in types] == types


async def test_stripped_fields(app, client, cdc: Codec, sim_cdc: Codec):
    enc_id, enc_val = await sim_cdc.encode('EdgeCase', {
        'deltaV': 100,  # tag 6
        'logged': 10,  # tag 7
        'strippedFields': [6],
    })
    dec_id, dec_val = await cdc.decode(enc_id, enc_val)
    assert dec_val['deltaV']['value'] is None
    assert dec_val['deltaV']['unit'] == 'delta_degC / second'
    assert dec_val['logged'] == 10
    assert 'strippedFields' not in dec_val.keys()

    dec_id, dec_val = await cdc.decode(enc_id, enc_val,
                                       CodecOpts(metadata=MetadataOpt.POSTFIX))
    assert dec_val['deltaV[delta_degC / second]'] is None


async def test_driven_fields(app, client, cdc: Codec):
    enc_id, enc_val = await cdc.encode('EdgeCase', {
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
    enc_id, enc_val = await cdc.encode('EdgeCase', {
        'drivenDevice': 10,
        'state': {
            'value[degC]': 10
        }
    })

    dec_id, dec_val = await cdc.decode(enc_id, enc_val, CodecOpts(metadata=MetadataOpt.POSTFIX))
    assert dec_val['drivenDevice<DS2413,driven>'] == 10
    assert dec_val['state']['value[degC]'] == pytest.approx(10, 0.01)


async def test_point_presence(app, client, cdc: Codec):
    enc_id_present, enc_val_present = await cdc.encode('SetpointProfile', {
        'points': [
            {'time': 0, 'temperature[degC]': 0},
            {'time': 10, 'temperature[degC]': 10},
        ]
    })

    enc_id_absent, enc_val_absent = await cdc.encode('SetpointProfile', {
        'points': [
            {'time': 10, 'temperature[degC]': 10},
        ]
    })

    assert enc_val_present != enc_val_absent

    dec_id_present, dec_val_present = await cdc.decode(enc_id_present, enc_val_present)
    dec_id_absent, dec_val_absent = await cdc.decode(enc_id_absent, enc_val_absent)

    assert dec_val_present['points'][0]['time'] == 0


async def test_compatible_types(app, client, cdc: Codec):
    tree = cdc.compatible_types()
    assert len(tree['TempSensorInterface']) > 0


async def test_enum_decoding(app, client, cdc: Codec):
    enc_id, enc_val = await cdc.encode('DigitalActuator', {
        'desiredState': 'STATE_ACTIVE',
    })
    dec_id, dec_val = await cdc.decode(enc_id, enc_val)
    assert dec_val['desiredState'] == 'STATE_ACTIVE'

    # Both strings and ints are valid input
    enc_id_alt, enc_val_alt = await cdc.encode('DigitalActuator', {
        'desiredState': 1,
    })
    assert enc_val_alt == enc_val

    dec_id, dec_val = await cdc.decode(enc_id, enc_val, CodecOpts(enums=ProtoEnumOpt.INT))
    assert dec_val['desiredState'] == 1
