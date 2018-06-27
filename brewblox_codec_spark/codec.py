"""
Generic entry point for all codecs.
Offers encoding and decoding of objects.
"""

from copy import deepcopy

from aiohttp import web
from brewblox_codec_spark.modifiers import Modifier
from brewblox_codec_spark.transcoders import (Decoded_, Encoded_, ObjType_,
                                              Transcoder)
from brewblox_service import brewblox_logger, features

LOGGER = brewblox_logger(__name__)


def setup(app: web.Application):
    features.add(app, Codec(app))


def get_codec(app: web.Application) -> 'Codec':
    return features.get(app, Codec)


class Codec(features.ServiceFeature):
    def __init__(self, app: web.Application):
        super().__init__(app)
        self._mod: Modifier = None

    async def startup(self, app: web.Application):
        self._mod = Modifier(app['config']['unit_system_file'])

    async def shutdown(self, *_):
        pass

    async def encode(self, obj_type: ObjType_, values: Decoded_) -> Encoded_:
        assert isinstance(values, dict), f'Unable to encode [{type(values).__name__}] values'
        return Transcoder.get(obj_type, self._mod).encode(deepcopy(values))

    async def decode(self, obj_type: ObjType_, encoded: Encoded_) -> Decoded_:
        assert isinstance(encoded, (bytes, list)), f'Unable to decode [{type(encoded).__name__}] values'
        return Transcoder.get(obj_type, self._mod).decode(encoded)
