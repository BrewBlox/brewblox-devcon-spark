"""
Tests brewblox codec
"""

from brewblox_devcon_spark.codec import _path_extension  # isort:skip

import pytest

from brewblox_devcon_spark import exceptions
from brewblox_devcon_spark.codec import codec

_path_extension.avoid_lint_errors()


@pytest.fixture
def app(app):
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
    print(encoded)


async def test_encode_errors(app, client, cdc):
    with pytest.raises(TypeError):
        await cdc.encode('OneWireTempSensor', None)

    with pytest.raises(exceptions.EncodeException):
        await cdc.encode('MAGIC', {})


async def test_decode_errors(app, client, cdc):
    with pytest.raises(TypeError):
        await cdc.decode('OneWireTempSensor', 'string')

    with pytest.raises(exceptions.DecodeException):
        await cdc.decode('MAGIC', b'\x00')
