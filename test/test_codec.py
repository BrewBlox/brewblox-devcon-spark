"""
Tests brewblox codec
"""

from brewblox_devcon_spark.codec import _path_extension  # isort:skip

import pytest
from brewblox_service import scheduler

from brewblox_devcon_spark import datastore, exceptions
from brewblox_devcon_spark.codec import codec

_path_extension.avoid_lint_errors()


@pytest.fixture
def app(app):
    app['config']['unit_defaults'] = ['degC']
    scheduler.setup(app)
    datastore.setup(app)
    codec.setup(app)
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
    assert await cdc.encode('InvalidObject', {'args': True}) == (0, b'\x00')
    assert await cdc.decode(0, b'\xAA') == ('InvalidObject', {})


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
