"""
Generic entry point for all codecs.
Offers encoding and decoding of objects.
"""

from copy import deepcopy
from typing import Awaitable, Callable, Tuple, Union

from aiohttp import web
from brewblox_service import brewblox_logger, features

from brewblox_codec_spark.modifiers import Modifier
from brewblox_codec_spark.transcoders import (Decoded_, Encoded_, ObjType_,
                                              Transcoder)

TranscodeFunc_ = Callable[
    [ObjType_, Union[Encoded_, Decoded_]],
    Awaitable[Tuple[ObjType_, Union[Encoded_, Decoded_]]]
]

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

    async def encode(self,
                     obj_type: ObjType_,
                     values: Decoded_
                     ) -> Awaitable[Tuple[ObjType_, Encoded_]]:
        """
        Encode given data to a serializable type.

        Does not guarantee perfect symmetry with `decode()`, only symmetric compatibility.
        `decode()` can correctly interpret the return values of `encode()`, and vice versa.

        Args:
            obj_type (ObjType_):
                The unique identifier of the codec type.
                This determines how `values` are encoded.

            values (Decoded_):
                Decoded representation of the message.

        Returns:
            Tuple[ObjType_, Encoded_]:
                Serializable values of both object type and values.
        """
        if not isinstance(values, dict):
            raise TypeError(f'Unable to encode [{type(values).__name__}] values')

        trc = Transcoder.get(obj_type, self._mod)
        return trc.type_int(), trc.encode(deepcopy(values))

    async def decode(self,
                     obj_type: ObjType_,
                     encoded: Encoded_
                     ) -> Awaitable[Tuple[ObjType_, Decoded_]]:
        """
        Decodes given data to a Python-compatible type.

        Does not guarantee perfect symmetry with `encode()`, only symmetric compatibility.
        `encode()` can correctly interpret the return values of `decode()`, and vice versa.

        Args:
            obj_type (ObjType_):
                The unique identifier of the codec type.
                This determines how `values` are decoded.

            values (Encoded_):
                Encoded representation of the message.

        Returns:
            Tuple[ObjType_, Decoded_]:
                Python-compatible values of both object type and values
        """
        if not isinstance(encoded, (bytes, list)):
            raise TypeError(f'Unable to decode [{type(encoded).__name__}] values')

        trc = Transcoder.get(obj_type, self._mod)
        return trc.type_str(), trc.decode(encoded)
