"""
Tests brewblox codec
"""

from brewblox_devcon_spark.codec import _path_extension  # isort:skip

import asyncio
from unittest.mock import ANY

import pytest
from brewblox_service import features, scheduler

from brewblox_devcon_spark import (commander_sim, datastore, device,
                                   exceptions, seeder, status)
from brewblox_devcon_spark.codec import codec

_path_extension.avoid_lint_errors()


@pytest.fixture
def app(app):
    status.setup(app)
    scheduler.setup(app)
    datastore.setup(app)
    commander_sim.setup(app)
    codec.setup(app)
    device.setup(app)
    seeder.setup(app)
    return app


@pytest.fixture
def cdc(app) -> codec.Codec:
    return codec.get_codec(app)


@pytest.fixture
def sim_cdc(app) -> codec.Codec:
    return features.get(app, key='sim_codec')


async def test_encode_system_objects(app, client, cdc):
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


async def test_encode_errors(app, client, cdc):
    with pytest.raises(TypeError):
        await cdc.encode('TempSensorOneWire', None)

    with pytest.raises(exceptions.EncodeException):
        await cdc.encode('MAGIC', {})

    with pytest.raises(exceptions.EncodeException):
        await cdc.encode('TempSensorOneWire', {'Galileo': 'thunderbolts and lightning'})


async def test_decode_errors(app, client, cdc):
    with pytest.raises(TypeError):
        await cdc.decode('TempSensorOneWire', 'string')

    type_int = await cdc.encode('TempSensorOneWire')
    assert await cdc.decode(type_int, b'very very frightening me') \
        == ('ErrorObject', {'error': ANY, 'type': 'TempSensorOneWire'})

    assert await cdc.decode(1e6, b'\x00') == ('ErrorObject', {'error': ANY, 'type': 1e6})
    assert await cdc.decode(1e6) == 'UnknownType'


async def test_invalid_object(app, client, cdc):
    assert await cdc.encode('Invalid', {'args': True}) == (0, b'\x00')
    assert await cdc.decode(0, b'\xAA') == ('Invalid', {})


async def test_encode_constraint(app, client, cdc):
    assert await cdc.decode('ActuatorPwm', b'\x00')
    assert await cdc.encode('ActuatorPwm', {
        'constrainedBy': {
            'constraints': [
                {'min': -100},
                {'max': 100},
            ],
        },
    })


async def test_encode_delta_sec(app, client, cdc):
    # Check whether [delta_temperature / time] can be converted
    enc_id, enc_val = await cdc.encode('EdgeCase', {
        'deltaV': 100,
    })
    dec_id, dec_val = await cdc.decode(enc_id, enc_val)
    assert dec_val['deltaV[delta_degC / second]'] == pytest.approx(100, 0.1)


async def test_transcode_interfaces(app, client, cdc):
    types = [
        'EdgeCase',
        'BalancerInterface',
        'SetpointSensorPair',
        'SetpointSensorPairInterface'
    ]
    assert [await cdc.decode(await cdc.encode(t)) for t in types] == types


async def test_stripped_fields(app, client, cdc, sim_cdc):
    enc_id, enc_val = await sim_cdc.encode('EdgeCase', {
        'deltaV': 100,  # tag 6
        'logged': 10,  # tag 7
        'strippedFields': [6],
    })
    dec_id, dec_val = await cdc.decode(enc_id, enc_val)
    assert dec_val['deltaV[delta_degC / second]'] is None
    assert dec_val['logged'] == 10
    assert 'strippedFields' not in dec_val.keys()


async def test_codec_config(app, client, cdc):
    state = status.get_status(app)
    await state.wait_synchronize()

    updated = cdc.update_unit_config({'Temp': 'degF'})
    assert updated['Temp'] == 'degF'
    assert cdc.get_unit_config() == updated

    # disconnect
    await state.on_disconnect()
    await asyncio.sleep(0.01)
    # connect
    await state.on_connect('codec test')
    await state.wait_synchronize()

    assert cdc.get_unit_config()['Temp'] == 'degC'


async def test_driven_fields(app, client, cdc):
    enc_id, enc_val = await cdc.encode('EdgeCase', {
        'drivenDevice': 10,
    })
    dec_id, dec_val = await cdc.decode(enc_id, enc_val)
    assert dec_val['drivenDevice<DS2413,driven>'] == 10


async def test_point_presence(app, client, cdc):
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


async def test_compatible_types(app, client, cdc):
    tree = cdc.compatible_types()
    assert len(tree['TempSensorInterface']) > 0
