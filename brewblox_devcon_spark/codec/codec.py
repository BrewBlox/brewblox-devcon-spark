"""
Generic entry point for all codecs.
Offers encoding and decoding of objects.
"""


import asyncio
from copy import deepcopy
from typing import Awaitable, Callable, Optional, Tuple, Union

from aiohttp import web
from brewblox_service import brewblox_logger, features, strex

from brewblox_devcon_spark import exceptions

from .modifiers import Modifier
from .opts import CodecOpts
from .transcoders import Decoded_, Encoded_, ObjType_, Transcoder
from .unit_conversion import get_converter

TranscodeFunc_ = Callable[
    [ObjType_, Union[Encoded_, Decoded_]],
    Awaitable[Tuple[ObjType_, Union[Encoded_, Decoded_]]]
]

LOGGER = brewblox_logger(__name__)


class Codec(features.ServiceFeature):
    def __init__(self, app: web.Application, strip_readonly=True):
        super().__init__(app)
        self._strip_readonly = strip_readonly
        self._mod: Modifier = None

    async def startup(self, app: web.Application):
        converter = get_converter(app)
        self._mod = Modifier(converter, self._strip_readonly)

    async def shutdown(self, app: web.Application):
        pass

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
                     values: Optional[Decoded_] = ...,
                     opts: Optional[CodecOpts] = None
                     ) -> Union[ObjType_, Tuple[ObjType_, Encoded_]]:
        """
        Encode given data to a serializable type.

        Does not guarantee perfect symmetry with `decode()`, only symmetric compatibility.
        `decode()` can correctly interpret the return values of `encode()`, and vice versa.

        Args:
            obj_type (ObjType_):
                The unique identifier of the codec type.
                This determines how `values` are encoded.

            values (Optional(Decoded_)):
                Decoded representation of the message.
                If not set, only encoded object type will be returned.

            opts (Optional[CodecOpts]):
                Additional options that are passed to the transcoder.

        Returns:
            ObjType_:
                If `values` is not set, only encoded object type is returned.

            Tuple[ObjType_, Encoded_]:
                Serializable values of both object type and values.
        """
        if not isinstance(values, (dict, type(...))):
            raise TypeError(f'Unable to encode [{type(values).__name__}] values')

        if opts is not None and not isinstance(opts, CodecOpts):
            raise TypeError(f'Invalid codec opts: {opts}')

        try:
            opts = opts or CodecOpts()
            trc = Transcoder.get(obj_type, self._mod)
            return trc.type_int() if values is ... \
                else (trc.type_int(), trc.encode(deepcopy(values), opts))
        except Exception as ex:
            msg = strex(ex)
            LOGGER.debug(msg, exc_info=True)
            raise exceptions.EncodeException(msg)

    async def decode(self,
                     obj_type: ObjType_,
                     values: Optional[Encoded_] = ...,
                     opts: Optional[CodecOpts] = None
                     ) -> Union[ObjType_, Tuple[ObjType_, Decoded_]]:
        """
        Decodes given data to a Python-compatible type.

        Does not guarantee perfect symmetry with `encode()`, only symmetric compatibility.
        `encode()` can correctly interpret the return values of `decode()`, and vice versa.

        Args:
            obj_type (ObjType_):
                The unique identifier of the codec type.
                This determines how `values` are decoded.

            values (Optional[Encoded_]):
                Encoded representation of the message.
                If not set, only decoded object type will be returned.

            opts (Optional[CodecOpts]):
                Additional options that are passed to the transcoder.

        Returns:
            ObjType_:
                If `values` is not set, only decoded object type is returned.

            Tuple[ObjType_, Decoded_]:
                Python-compatible values of both object type and values.
        """
        if not isinstance(values, (bytes, list, type(...))):
            raise TypeError(f'Unable to decode [{type(values).__name__}] values')

        if opts is not None and not isinstance(opts, CodecOpts):
            raise TypeError(f'Invalid codec opts: {opts}')

        type_name = obj_type
        no_content = values == ...

        try:
            opts = opts or CodecOpts()
            trc = Transcoder.get(obj_type, self._mod)
            type_name = trc.type_str()
            return type_name if no_content else (type_name, trc.decode(values, opts))

        except asyncio.CancelledError:  # pragma: no cover
            raise

        except Exception as ex:
            msg = strex(ex)
            LOGGER.debug(msg, exc_info=True)
            return 'UnknownType' if no_content else ('ErrorObject', {'error': msg, 'type': type_name})


def setup(app: web.Application):
    features.add(app, Codec(app))


def get_codec(app: web.Application) -> Codec:
    return features.get(app, Codec)
