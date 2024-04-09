"""
Default exports for codec module
"""

import logging
from base64 import b64decode, b64encode
from contextvars import ContextVar
from typing import Optional

from google.protobuf import json_format

from .. import exceptions, utils
from ..models import (DecodedPayload, EncodedPayload, IntermediateRequest,
                      IntermediateResponse, ReadMode)
from . import lookup, pb2, time_utils, unit_conversion
from .processor import ProtobufProcessor

DEPRECATED_TYPE_INT = 65533
DEPRECATED_TYPE_STR = 'DeprecatedObject'
UNKNOWN_TYPE_STR = 'UnknownType'
ERROR_TYPE_STR = 'ErrorObject'

LOGGER = logging.getLogger(__name__)
CV: ContextVar['Codec'] = ContextVar('codec.Codec')


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


class Codec:
    def __init__(self, filter_values=True):
        self._processor = ProtobufProcessor(filter_values)

    def encode_request(self, request: IntermediateRequest) -> str:
        try:
            message = pb2.command_pb2.Request()
            json_format.ParseDict(request.model_dump(mode='json'), message)
            return b64encode(message.SerializeToString()).decode()

        except Exception as ex:
            msg = utils.strex(ex)
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
            msg = utils.strex(ex)
            LOGGER.debug(msg, exc_info=True)
            raise exceptions.DecodeException(msg)

    def encode_response(self, response: IntermediateResponse) -> str:
        try:
            message = pb2.command_pb2.Response()
            json_format.ParseDict(response.model_dump(mode='json'), message)
            return b64encode(message.SerializeToString()).decode()

        except Exception as ex:
            msg = utils.strex(ex)
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
            msg = utils.strex(ex)
            LOGGER.debug(msg, exc_info=True)
            raise exceptions.DecodeException(msg)

    def encode_payload(self,
                       payload: DecodedPayload,
                       filter_values: bool | None = None) -> EncodedPayload:
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
                impl = next((v for v in lookup.CV_COMBINED.get()
                             if v.type_str == payload.blockType))
                return EncodedPayload(
                    blockId=payload.blockId,
                    blockType=impl.type_int,
                )

            # Payload contains data
            impl = next((v for v in lookup.CV_OBJECTS.get()
                         if v.type_str == payload.blockType
                         and v.subtype_str == payload.subtype))

            message = impl.message_cls()
            payload = self._processor.pre_encode(message.DESCRIPTOR,
                                                 payload.model_copy(deep=True),
                                                 filter_values=filter_values)
            json_format.ParseDict(payload.content, message)
            content: str = b64encode(message.SerializeToString()).decode()

            return EncodedPayload(
                blockId=payload.blockId,
                blockType=impl.type_int,
                subtype=impl.subtype_int,
                content=content,
                maskMode=payload.maskMode,
                maskFields=payload.maskFields
            )

        except StopIteration:
            msg = f'No codec entry found for {payload.blockType}.{payload.subtype}'
            LOGGER.debug(msg, exc_info=True)
            raise exceptions.EncodeException(msg)

        except Exception as ex:
            msg = utils.strex(ex)
            LOGGER.debug(msg, exc_info=True)
            raise exceptions.EncodeException(msg)

    def decode_payload(self,
                       payload: EncodedPayload, /,
                       mode: ReadMode = ReadMode.DEFAULT,
                       filter_values: bool | None = None,
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
            impl = next((v for v in lookup.CV_OBJECTS.get()
                         if payload.blockType in [v.type_str, v.type_int]
                         and payload.subtype in [v.subtype_str, v.subtype_int]), None)

            if impl:
                # We have an object lookup, and can decode the content
                message = impl.message_cls()
                message.ParseFromString(b64decode(payload.content))
                content: dict = json_format.MessageToDict(
                    message=message,
                    preserving_proto_field_name=True,
                    including_default_value_fields=True,
                    use_integers_for_enums=(mode in (ReadMode.STORED, ReadMode.LOGGED)),
                )
                decoded = DecodedPayload(
                    blockId=payload.blockId,
                    blockType=impl.type_str,
                    subtype=impl.subtype_str,
                    content=content,
                    maskMode=payload.maskMode,
                    maskFields=payload.maskFields
                )
                return self._processor.post_decode(message.DESCRIPTOR,
                                                   decoded,
                                                   mode=mode,
                                                   filter_values=filter_values)

            # No object lookup found. Try the interfaces.
            intf_impl = next((v for v in lookup.CV_INTERFACES.get()
                              if payload.blockType in [v.type_str, v.type_int]), None)

            if intf_impl:
                return DecodedPayload(
                    blockId=payload.blockId,
                    blockType=intf_impl.type_str,
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
            msg = utils.strex(ex)
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


def setup():
    lookup.setup()
    unit_conversion.setup()
    CV.set(Codec())


__all__ = [
    'split_type',
    'join_type',

    'Codec',
    'setup',
    'CV',

    'ProtobufProcessor'

    # utils
    'bloxfield',
    'time_utils',
]
