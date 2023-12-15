"""
REST API for system debugging
"""

import logging

from fastapi import APIRouter

from .. import codec
from ..models import (DecodedPayload, EncodedMessage, EncodedPayload,
                      IntermediateRequest, IntermediateResponse)

LOGGER = logging.getLogger(__name__)
router = APIRouter(prefix='/_debug', tags=['Debug'])


@router.post('/encode_request')
async def debug_encode_request(args: IntermediateRequest) -> EncodedMessage:
    """
    Encode a Request object to a base64 string.

    Te object encoded to protobuf bytes.
    The bytes are encoded as base64 to make them ASCII-safe.

    Included payloads must have been encoded using /_debug/encode_payload.
    """
    message = codec.CV.get().encode_request(args)
    return EncodedMessage(message=message)


@router.post('/decode_request')
async def debug_decode_request(args: EncodedMessage) -> IntermediateRequest:
    """
    Decode a Request object from a base64 string.

    The base64 string is converted to bytes.
    The bytes are decoded using protobuf.

    Included payloads must be decoded using /_debug/decode_payload
    """
    request = codec.CV.get().decode_request(args.message)
    return request


@router.post('/encode_response')
async def debug_encode_response(args: IntermediateResponse) -> EncodedMessage:
    """
    Encode a Response object to a base64 string.

    Te object encoded to protobuf bytes.
    The bytes are encoded as base64 to make them ASCII-safe.

    Included payloads must have been encoded using /_debug/encode_payload.
    """
    message = codec.CV.get().encode_response(args)
    return EncodedMessage(message=message)


@router.post('/decode_response')
async def debug_decode_response(args: EncodedMessage) -> IntermediateResponse:
    """
    Decode a Response object from a base64 string.

    The base64 string is converted to bytes.
    The bytes are decoded using protobuf.

    Included payloads must be decoded using /_debug/decode_payload
    """
    response = codec.CV.get().decode_response(args.message)
    return response


@router.post('/encode_payload')
async def debug_encode_payload(args: DecodedPayload) -> EncodedPayload:
    """
    Encode a Payload object.

    `content` is encoded to protobuf bytes,
    and then encoded as base64 to make it ASCII-safe.

    This operation is symmetrical with /_debug/decode_payload.
    """
    payload = codec.CV.get().encode_payload(args)
    return payload


@router.post('/decode_payload')
async def debug_decode_payload(args: EncodedPayload) -> DecodedPayload:
    """
    Decode a Payload object.

    `content` is converted to bytes,
    and then decoded using protobuf.

    This operation is symmetrical with /_debug/encode_payload
    """
    payload = codec.CV.get().decode_payload(args)
    return payload
