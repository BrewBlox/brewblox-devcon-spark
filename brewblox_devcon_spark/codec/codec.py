"""
Generic entry point for all codecs.
Offers encoding and decoding of objects.
"""

from copy import deepcopy
from typing import Awaitable, Callable, Dict, Tuple, Union

from aiohttp import web
from brewblox_service import brewblox_logger, features

from brewblox_devcon_spark import datastore, exceptions
from brewblox_devcon_spark.codec.modifiers import Modifier
from brewblox_devcon_spark.codec.transcoders import (Decoded_, Encoded_,
                                                     ObjType_, Transcoder)
from brewblox_devcon_spark.codec.unit_conversion import (UNIT_ALTERNATIVES,
                                                         UnitConverter)

TranscodeFunc_ = Callable[
    [ObjType_, Union[Encoded_, Decoded_]],
    Awaitable[Tuple[ObjType_, Union[Encoded_, Decoded_]]]
]
UNIT_CONFIG_KEY = 'user_units'

LOGGER = brewblox_logger(__name__)


def setup(app: web.Application):
    features.add(app, Codec(app))


def get_codec(app: web.Application) -> 'Codec':
    return features.get(app, Codec)


class Codec(features.ServiceFeature):
    def __init__(self, app: web.Application, strip_readonly=True):
        super().__init__(app)
        self._strip_readonly = strip_readonly
        self._converter: UnitConverter = None
        self._mod: Modifier = None

    async def startup(self, app: web.Application):
        self._converter = UnitConverter()
        self._mod = Modifier(self._converter, self._strip_readonly)

        try:
            with datastore.get_config(app).open() as cfg:
                self._converter.user_units = cfg.get(UNIT_CONFIG_KEY, {})
            LOGGER.info('Loaded user-defined units')
        except Exception as ex:
            LOGGER.info(f'Failed to load user-defined units: {type(ex).__name__}({ex})', exc_info=True)

    async def shutdown(self, *_):
        pass

    def get_unit_config(self) -> Dict[str, str]:
        return self._converter.user_units

    def update_unit_config(self, units: Dict[str, str]) -> Dict[str, str]:
        self._converter.user_units = units
        updated = self._converter.user_units
        with datastore.get_config(self.app).open() as config:
            config[UNIT_CONFIG_KEY] = updated
        return updated

    def get_unit_alternatives(self):
        return UNIT_ALTERNATIVES

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

        try:
            trc = Transcoder.get(obj_type, self._mod)
            return trc.type_int(), trc.encode(deepcopy(values))
        except Exception as ex:
            msg = f'{type(ex).__name__}({ex})'
            LOGGER.debug(msg, exc_info=True)
            raise exceptions.EncodeException(msg)

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

        try:
            trc = Transcoder.get(obj_type, self._mod)
            return trc.type_str(), trc.decode(encoded)
        except Exception as ex:
            msg = f'{type(ex).__name__}({ex})'
            LOGGER.debug(msg, exc_info=True)
            raise exceptions.DecodeException(msg)
