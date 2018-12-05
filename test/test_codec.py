"""
Tests brewblox codec
"""

from brewblox_devcon_spark.codec import _path_extension  # isort:skip

import asyncio

import pytest
from brewblox_service import scheduler

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
            'type': 'Profiles',
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


async def test_decode_errors(app, client, cdc):
    with pytest.raises(TypeError):
        await cdc.decode('TempSensorOneWire', 'string')

    with pytest.raises(exceptions.DecodeException):
        await cdc.decode('MAGIC', b'\x00')


async def test_invalid_object(app, client, cdc):
    assert await cdc.encode('InvalidLink', {'args': True}) == (0, b'\x00')
    assert await cdc.decode(0, b'\xAA') == ('InvalidLink', {})


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
        'BalancerLink',
        'SetpointSensorPair',
        'SetpointSensorPairLink'
    ]
    assert [await cdc.decode(await cdc.encode(t)) for t in types] == types


async def test_codec_config(app, client, cdc):
    state = status.get_status(app)

    updated = cdc.update_unit_config({'Temp': 'degF'})
    assert updated['Temp'] == 'degF'
    assert cdc.get_unit_config() == updated

    # disconnect
    state.connected.clear()
    state.disconnected.set()
    await asyncio.sleep(0.01)
    # connect
    state.disconnected.clear()
    state.connected.set()
    await asyncio.sleep(0.01)

    assert cdc.get_unit_config()['Temp'] == 'degC'
