"""
Generic entry point for all codecs.
Offers encoding and decoding of objects.
"""


from copy import deepcopy
from typing import Awaitable, Callable, Dict, Optional, Tuple, Union

from aiohttp import web
from brewblox_service import brewblox_logger, features

from brewblox_devcon_spark import datastore, exceptions
from brewblox_devcon_spark.codec.modifiers import STRIP_UNLOGGED_KEY, Modifier
from brewblox_devcon_spark.codec.transcoders import (Decoded_, Encoded_,
                                                     ObjType_, Transcoder)
from brewblox_devcon_spark.codec.unit_conversion import (UNIT_ALTERNATIVES,
                                                         UnitConverter)

TranscodeFunc_ = Callable[
    [ObjType_, Union[Encoded_, Decoded_]],
    Awaitable[Tuple[ObjType_, Union[Encoded_, Decoded_]]]
]
UNIT_CONFIG_KEY = 'user_units'
STRIP_UNLOGGED_KEY = STRIP_UNLOGGED_KEY

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
        datastore.get_config(app).subscribe(self._on_config_change)

    async def shutdown(self, app: web.Application):
        pass

    def get_unit_config(self) -> Dict[str, str]:
        return self._converter.user_units

    def _on_config_change(self, config):
        self._converter.user_units = config.get(UNIT_CONFIG_KEY, {})
        config[UNIT_CONFIG_KEY] = self._converter.user_units

    def update_unit_config(self, units: Dict[str, str] = None) -> Dict[str, str]:
        self._converter.user_units = units
        updated = self._converter.user_units
        with datastore.get_config(self.app).open() as config:
            config[UNIT_CONFIG_KEY] = updated
        return updated

    def get_unit_alternatives(self):
        return UNIT_ALTERNATIVES

    def compatible_types(self) -> Awaitable[dict]:
        """
        Compiles lists of implementers of type interfaces.

        Returns:
            Dict[str, List[str]]:
                The key is the name of the interface type.
                The value is a list of types that implement that interface.
        """
        return Transcoder.type_tree(self._mod)

    async def encode(self,
                     obj_type: ObjType_,
                     values: Decoded_ = ...,
                     opts: Optional[dict] = None
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

            opts (Optional[dict]):
                Additional options that are passed to the transcoder.

        Returns:
            Tuple[ObjType_, Encoded_]:
                Serializable values of both object type and values.
        """
        if not isinstance(values, (dict, type(...))):
            raise TypeError(f'Unable to encode [{type(values).__name__}] values')

        try:
            opts = opts or {}
            trc = Transcoder.get(obj_type, self._mod)
            return trc.type_int() if values is ... \
                else (trc.type_int(), trc.encode(deepcopy(values), opts))
        except Exception as ex:
            msg = f'{type(ex).__name__}({ex})'
            LOGGER.debug(msg, exc_info=True)
            raise exceptions.EncodeException(msg)

    async def decode(self,
                     obj_type: ObjType_,
                     encoded: Encoded_ = ...,
                     opts: Optional[dict] = None
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

            opts (Optional[dict]):
                Additional options that are passed to the transcoder.

        Returns:
            Tuple[ObjType_, Decoded_]:
                Python-compatible values of both object type and values
        """
        if not isinstance(encoded, (bytes, list, type(...))):
            raise TypeError(f'Unable to decode [{type(encoded).__name__}] values')

        type_name = obj_type
        no_content = encoded == ...

        try:
            opts = opts or {}
            trc = Transcoder.get(obj_type, self._mod)
            type_name = trc.type_str()
            return type_name if no_content else (type_name, trc.decode(encoded, opts))

        except Exception as ex:
            msg = f'{type(ex).__name__}({ex})'
            LOGGER.debug(msg, exc_info=True)
            return 'UnknownType' if no_content else ('ErrorObject', {'error': msg, 'type': type_name})
