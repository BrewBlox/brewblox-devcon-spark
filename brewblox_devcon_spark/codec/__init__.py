"""
Default exports for codec module
"""

from base64 import b64decode, b64encode
from copy import deepcopy
from typing import Optional, Union

from aiohttp import web
from brewblox_service import brewblox_logger, features, strex

from brewblox_devcon_spark import exceptions

from . import unit_conversion
from .opts import DecodeOpts, FilterOpt, MetadataOpt, ProtoEnumOpt
from .processor import ProtobufProcessor
from .transcoders import (REQUEST_TYPE, REQUEST_TYPE_INT,  # noqa: F401
                          RESPONSE_TYPE, RESPONSE_TYPE_INT, Identifier_,
                          Transcoder)

LOGGER = brewblox_logger(__name__)


class Codec(features.ServiceFeature):
    def __init__(self, app: web.Application, strip_readonly=True):
        super().__init__(app)
        self._proto_proc = ProtobufProcessor(unit_conversion.fget(app),
                                             strip_readonly)

    async def encode(self,
                     identifier: Identifier_,
                     data: Optional[dict],
                     ) -> tuple[Identifier_, Optional[str]]:
        """
        Encode given data to a serializable type.

        Does not guarantee perfect symmetry with `decode()`, only symmetric compatibility.
        `decode()` can correctly interpret the return values of `encode()`, and vice versa.

        Args:
            identifier (Identifier_):
                The fully qualified identifier of the codec type.
                This determines how `data` is encoded.

            data (Optional(dict)):
                Decoded representation of the message.
                If not set, only encoded object type will be returned.

        Returns:
            tuple[Identifier, Optional[str]]:
                Numeric identifier, and encoded data.
                Data will be None if it was None in args.
        """
        if data is not None and not isinstance(data, dict):
            raise TypeError(f'Unable to encode [{type(data).__name__}]')

        try:
            trc = Transcoder.get(identifier, self._proto_proc)
            encoded_identifier = (trc.type_int(), trc.subtype_int())
            if data is None:
                return (encoded_identifier, None)
            else:
                return (encoded_identifier, b64encode(trc.encode(deepcopy(data))).decode())

        except Exception as ex:
            msg = strex(ex)
            LOGGER.debug(msg, exc_info=True)
            raise exceptions.EncodeException(msg)

    async def decode(self,
                     identifier: Identifier_,
                     data: Optional[Union[str, bytes]],
                     opts: Optional[DecodeOpts] = None
                     ) -> tuple[Identifier_, Optional[dict]]:
        """
        Decodes given data to a Python-compatible type.

        Does not guarantee perfect symmetry with `encode()`, only symmetric compatibility.
        `encode()` can correctly interpret the return values of `decode()`, and vice versa.

        Args:
            identifier (Identifier_):
                The unique identifier of the codec type.
                This determines how `values` are decoded.

            data (Optional[Union[str, bytes]]):
                Base-64 representation of the message bytes.
                A byte string is acceptable.

            opts (Optional[DecodeOpts]):
                Additional options that are passed to the transcoder.

        Returns:
            tuple[Identifier_, Optional[dict]]:
                Decoded identifier, and decoded data.
                Data will be None if it was None in args.
        """
        if data is not None and not isinstance(data, (str, bytes)):
            raise TypeError(f'Unable to decode [{type(data).__name__}]')

        if opts is not None and not isinstance(opts, DecodeOpts):
            raise TypeError(f'Invalid codec opts: {opts}')

        decoded_identifier = identifier

        try:
            opts = opts or DecodeOpts()
            trc = Transcoder.get(identifier, self._proto_proc)
            decoded_identifier = (trc.type_str(), trc.subtype_str())
            if data is None:
                return (decoded_identifier, None)
            else:
                data = data if isinstance(data, str) else data.decode()
                data = b''.join((b64decode(subs) for subs in data.split(',')))
                return (decoded_identifier, trc.decode(data, opts))

        except Exception as ex:
            msg = strex(ex)
            LOGGER.debug(msg, exc_info=True)
            if data is None:
                return (('UnknownType', None), None)
            else:
                return (('ErrorObject', None), {'error': msg, 'identifier': decoded_identifier})

    async def implements(self,
                         identifier: Identifier_,
                         ) -> list[str]:
        """
        Gets (interface) types implemented by identifier.

        Args:
            identifier (Identifier_):
                The unique identifier of the codec type.

        Return:
            list[str]:
                All blockType values implemented by the transcoder.
                Corresponds to brewblox_msg.impl in protobuf.
        """
        trc = Transcoder.get(identifier, self._proto_proc)
        return trc.type_impl()


def setup(app: web.Application):
    unit_conversion.setup(app)
    features.add(app, Codec(app))


def fget(app: web.Application) -> Codec:
    return features.get(app, Codec)


__all__ = [
    'Codec',
    'setup',
    'fget',

    'DecodeOpts',
    'ProtoEnumOpt',
    'FilterOpt',
    'MetadataOpt',
    'ProtobufProcessor'

    # Const
    'REQUEST_TYPE',
    'RESPONSE_TYPE',
    'REQUEST_TYPE_INT',
    'RESPONSE_TYPE_INT',
]
