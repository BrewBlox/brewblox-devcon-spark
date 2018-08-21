"""
Tests brewblox codec
"""

from brewblox_codec_spark import _path_extension  # isort:skip

import pytest

from brewblox_codec_spark import codec

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
            'type': 'OneWireBus',
            'data': {}
        }
    ]

    encoded = [await cdc.encode(o['type'], o['data']) for o in objects]
    print(encoded)
