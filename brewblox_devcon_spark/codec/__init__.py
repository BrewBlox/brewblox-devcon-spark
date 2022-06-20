"""
Default exports for codec module
"""

import json
from base64 import b64decode, b64encode
from typing import Optional

from aiohttp import web
from brewblox_service import brewblox_logger, features, strex
from google.protobuf import json_format

from brewblox_devcon_spark import exceptions
from brewblox_devcon_spark.models import (DecodedPayload, EncodedPayload,
                                          IntermediateRequest,
                                          IntermediateResponse)

from . import pb2, time_utils, unit_conversion
from .lookup import INTERFACE_LOOKUPS, OBJECT_LOOKUPS
from .opts import DecodeOpts, FilterOpt, MetadataOpt, ProtoEnumOpt
from .processor import ProtobufProcessor

DEPRECATED_TYPE_INT = 65533
DEPRECATED_TYPE_STR = 'DeprecatedObject'
LOGGER = brewblox_logger(__name__)


def split_type(type_str: str) -> tuple[str, Optional[str]]:
    if '.' in type_str:
        return tuple(type_str.split('.', 1))
    else:
        return type_str, None


def join_type(blockType: str, subtype: Optional[str]) -> str:
    if subtype:
        return f'{blockType}.{subtype}'
    else:
        return blockType


class Codec(features.ServiceFeature):
    def __init__(self, app: web.Application, strip_readonly=True):
        super().__init__(app)
        self._processor = ProtobufProcessor(unit_conversion.fget(app),
                                            strip_readonly)

    def encode_request(self, request: IntermediateRequest) -> str:
        try:
            message = pb2.command_pb2.Request()
            json_format.ParseDict(request.clean_dict(), message)
            return b64encode(message.SerializeToString()).decode()

        except Exception as ex:
            msg = strex(ex)
            LOGGER.debug(msg, exc_info=True)
            raise exceptions.EncodeException(msg)

    def decode_request(self, b64_encoded: str) -> IntermediateRequest:
        try:
            data = b''.join((b64decode(subs) for subs in b64_encoded.split(',')))

            message = pb2.command_pb2.Request()
            message.ParseFromString(data)
            decoded: dict = json_format.MessageToDict(
                message=message,
                preserving_proto_field_name=True,
                including_default_value_fields=True,
                use_integers_for_enums=False
            )

            return IntermediateRequest(**decoded)

        except Exception as ex:
            msg = strex(ex)
            LOGGER.debug(msg, exc_info=True)
            raise exceptions.DecodeException(msg)

    def encode_response(self, response: IntermediateResponse) -> str:
        try:
            message = pb2.command_pb2.Response()
            json_format.ParseDict(response.clean_dict(), message)
            return b64encode(message.SerializeToString()).decode()

        except Exception as ex:
            msg = strex(ex)
            LOGGER.debug(msg, exc_info=True)
            raise exceptions.EncodeException(msg)

    def decode_response(self, b64_encoded: str) -> IntermediateResponse:
        try:
            data = b''.join((b64decode(subs) for subs in b64_encoded.split(',')))

            message = pb2.command_pb2.Response()
            message.ParseFromString(data)
            decoded: dict = json_format.MessageToDict(
                message=message,
                preserving_proto_field_name=True,
                including_default_value_fields=True,
                use_integers_for_enums=False
            )

            return IntermediateResponse(**decoded)

        except Exception as ex:
            msg = strex(ex)
            LOGGER.debug(msg, exc_info=True)
            raise exceptions.DecodeException(msg)

    def encode_payload(self, payload: DecodedPayload) -> EncodedPayload:
        try:
            # No encoding required
            if payload.blockType is None:
                return EncodedPayload(
                    blockId=payload.blockId,
                )

            if payload.blockType == DEPRECATED_TYPE_STR:
                actual_id = payload.content['actualId']
                content_bytes = actual_id.to_bytes(2, 'little')
                return EncodedPayload(
                    blockId=payload.blockId,
                    blockType=DEPRECATED_TYPE_INT,
                    content=b64encode(content_bytes).decode(),
                )

            # Interface-only payload
            if payload.content is None:
                lookup = next((v for v in INTERFACE_LOOKUPS
                               if v.type_str == payload.blockType))
                return EncodedPayload(
                    blockId=payload.blockId,
                    blockType=payload.blockType,
                )

            # Payload contains data
            lookup = next((v for v in OBJECT_LOOKUPS
                           if v.type_str == payload.blockType
                           and v.subtype_str == payload.subtype))

            message = lookup.message_cls()
            payload = self._processor.pre_encode(message.DESCRIPTOR,
                                                 payload.copy(deep=True))
            json_format.ParseDict(payload.content, message)
            content: str = b64encode(message.SerializeToString()).decode()

            return EncodedPayload(
                blockId=payload.blockId,
                blockType=lookup.type_int,
                subtype=lookup.subtype_int,
                content=content,
                mask=payload.mask,
                maskMode=payload.maskMode,
            )

        except StopIteration:
            msg = f'No codec entry found for {payload.blockType}.{payload.subtype}'
            LOGGER.debug(msg, exc_info=True)
            raise exceptions.EncodeException(msg)

        except Exception as ex:
            msg = strex(ex)
            LOGGER.debug(msg, exc_info=True)
            raise exceptions.EncodeException(msg)

    def decode_payload(self,
                       payload: EncodedPayload,
                       /,
                       opts: DecodeOpts = DecodeOpts(),
                       ) -> DecodedPayload:
        try:
            # No decoding required
            if not payload.blockType:
                return DecodedPayload(
                    blockId=payload.blockId
                )

            if payload.blockType == DEPRECATED_TYPE_INT:
                content_bytes = b64decode(payload.content)
                content = {'actualId': int.from_bytes(content_bytes, 'little')}
                return DecodedPayload(
                    blockId=payload.blockId,
                    blockType=DEPRECATED_TYPE_STR,
                    content=content
                )

            # First, try to find an object lookup
            lookup = next((v for v in OBJECT_LOOKUPS
                           if payload.blockType in [v.type_str, v.type_int]
                           and payload.subtype in [v.subtype_str, v.subtype_int]), None)

            # No object lookup found. Try the interfaces.
            if not lookup:
                lookup = next((v for v in INTERFACE_LOOKUPS
                               if payload.blockType in [v.type_str, v.type_int]))
                return DecodedPayload(
                    blockId=payload.blockId,
                    blockType=lookup.type_str,
                )

            # We have an object lookup, and can decode the content
            int_enum = opts.enums == ProtoEnumOpt.INT
            message = lookup.message_cls()
            message.ParseFromString(b64decode(payload.content))
            content: dict = json_format.MessageToDict(
                message=message,
                preserving_proto_field_name=True,
                including_default_value_fields=True,
                use_integers_for_enums=int_enum,
            )
            decoded = DecodedPayload(
                blockId=payload.blockId,
                blockType=lookup.type_str,
                subtype=lookup.subtype_str,
                content=content,
                mask=payload.mask,
                maskMode=payload.maskMode,
            )
            return self._processor.post_decode(message.DESCRIPTOR, decoded, opts)

        except StopIteration:
            msg = f'No codec entry found for {payload.blockType}.{payload.subtype}'
            LOGGER.debug(msg, exc_info=True)
            raise exceptions.DecodeException(msg)

        except Exception as ex:
            msg = strex(ex)
            LOGGER.debug(msg, exc_info=True)
            raise exceptions.DecodeException(msg)

    # def encode(self,
    #                  identifier: Identifier_,
    #                  data: Optional[dict],
    #                  ) -> tuple[Identifier_, Optional[str]]:
    #     """
    #     Encode given data to a serializable type.

    #     Does not guarantee perfect symmetry with `decode()`, only symmetric compatibility.
    #     `decode()` can correctly interpret the return values of `encode()`, and vice versa.

    #     Args:
    #         identifier (Identifier_):
    #             The fully qualified identifier of the codec type.
    #             This determines how `data` is encoded.

    #         data (Optional(dict)):
    #             Decoded representation of the message.
    #             If not set, only encoded object type will be returned.

    #     Returns:
    #         tuple[Identifier, Optional[str]]:
    #             Numeric identifier, and encoded data.
    #             Data will be None if it was None in args.
    #     """
    #     if data is not None and not isinstance(data, dict):
    #         raise TypeError(f'Unable to encode [{type(data).__name__}]')

    #     try:
    #         trc = Transcoder.get(identifier, self._processor)
    #         encoded_identifier = (trc.type_int(), trc.subtype_int())
    #         if data is None:
    #             return (encoded_identifier, None)
    #         else:
    #             return (encoded_identifier, b64encode(trc.encode(deepcopy(data))).decode())

    #     except Exception as ex:
    #         msg = strex(ex)
    #         LOGGER.debug(msg, exc_info=True)
    #         raise exceptions.EncodeException(msg)

    # def decode(self,
    #                  identifier: Identifier_,
    #                  data: Optional[Union[str, bytes]],
    #                  opts: Optional[DecodeOpts] = None
    #                  ) -> tuple[Identifier_, Optional[dict]]:
    #     """
    #     Decodes given data to a Python-compatible type.

    #     Does not guarantee perfect symmetry with `encode()`, only symmetric compatibility.
    #     `encode()` can correctly interpret the return values of `decode()`, and vice versa.

    #     Args:
    #         identifier (Identifier_):
    #             The unique identifier of the codec type.
    #             This determines how `values` are decoded.

    #         data (Optional[Union[str, bytes]]):
    #             Base-64 representation of the message bytes.
    #             A byte string is acceptable.

    #         opts (Optional[DecodeOpts]):
    #             Additional options that are passed to the transcoder.

    #     Returns:
    #         tuple[Identifier_, Optional[dict]]:
    #             Decoded identifier, and decoded data.
    #             Data will be None if it was None in args.
    #     """
    #     if data is not None and not isinstance(data, (str, bytes)):
    #         raise TypeError(f'Unable to decode [{type(data).__name__}]')

    #     if opts is not None and not isinstance(opts, DecodeOpts):
    #         raise TypeError(f'Invalid codec opts: {opts}')

    #     decoded_identifier = identifier

    #     try:
    #         opts = opts or DecodeOpts()
    #         trc = Transcoder.get(identifier, self._processor)
    #         decoded_identifier = (trc.type_str(), trc.subtype_str())
    #         if data is None:
    #             return (decoded_identifier, None)
    #         else:
    #             data = data if isinstance(data, str) else data.decode()
    #             data = b''.join((b64decode(subs) for subs in data.split(',')))
    #             return (decoded_identifier, trc.decode(data, opts))

    #     except Exception as ex:
    #         msg = strex(ex)
    #         LOGGER.debug(msg, exc_info=True)
    #         if data is None:
    #             return (('UnknownType', None), None)
    #         else:
    #             return (('ErrorObject', None), {'error': msg, 'identifier': decoded_identifier})

    # def implements(self,
    #                      identifier: Identifier_,
    #                      ) -> list[str]:
    #     """
    #     Gets (interface) types implemented by identifier.

    #     Args:
    #         identifier (Identifier_):
    #             The unique identifier of the codec type.

    #     Return:
    #         list[str]:
    #             All blockType values implemented by the transcoder.
    #             Corresponds to brewblox_msg.impl in protobuf.
    #     """
    #     trc = Transcoder.get(identifier, self._processor)
    #     return trc.type_impl()


def setup(app: web.Application):
    unit_conversion.setup(app)
    features.add(app, Codec(app))


def fget(app: web.Application) -> Codec:
    return features.get(app, Codec)


__all__ = [
    'split_type',
    'join_type',

    'Codec',
    'setup',
    'fget',

    'DecodeOpts',
    'ProtoEnumOpt',
    'FilterOpt',
    'MetadataOpt',
    'ProtobufProcessor'

    # utils
    'bloxfield',
    'time_utils',
]
