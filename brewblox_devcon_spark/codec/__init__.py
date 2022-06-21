"""
Default exports for codec module
"""

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
UNKNOWN_TYPE_STR = 'UnknownType'
ERROR_TYPE_STR = 'ErrorObject'
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
                    blockType=lookup.type_int,
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

            if lookup:
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

            # No object lookup found. Try the interfaces.
            intf_lookup = next((v for v in INTERFACE_LOOKUPS
                                if payload.blockType in [v.type_str, v.type_int]), None)

            if intf_lookup:
                return DecodedPayload(
                    blockId=payload.blockId,
                    blockType=intf_lookup.type_str,
                )

            # No lookup of any kind found
            # We're decoding (returned) data, so would rather return a stub than raise an error
            msg = f'No codec entry found for {payload.blockType}.{payload.subtype}'
            LOGGER.debug(msg, exc_info=True)
            return DecodedPayload(
                blockId=payload.blockId,
                blockType=UNKNOWN_TYPE_STR,
                content={
                    'error': msg,
                },
            )

        except Exception as ex:
            msg = strex(ex)
            LOGGER.debug(msg, exc_info=True)
            return DecodedPayload(
                blockId=payload.blockId,
                blockType=ERROR_TYPE_STR,
                content={
                    'error': msg,
                    'blockType': payload.blockType,
                    'subtype': payload.subtype,
                },
            )


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
