"""
REST API for system debugging
"""

from aiohttp import web
from aiohttp_pydantic import PydanticView
from aiohttp_pydantic.oas.typing import r200
from brewblox_service import brewblox_logger

from brewblox_devcon_spark import codec
from brewblox_devcon_spark.models import (DecodedPayload, EncodedMessage,
                                          EncodedPayload, IntermediateRequest,
                                          IntermediateResponse)

LOGGER = logging.getLogger(__name__)
routes = web.RouteTableDef()


def setup(app: web.Application):
    app.router.add_routes(routes)


class CodecView(PydanticView):
    def __init__(self, request: web.Request) -> None:
        super().__init__(request)
        self.codec = codec.fget(request.app)


@routes.view('/_debug/encode_request')
class EncodeRequestView(CodecView):
    async def post(self, args: IntermediateRequest) -> r200[EncodedMessage]:
        """
        Encode a Request object to a base64 string.

        Te object encoded to protobuf bytes.
        The bytes are encoded as base64 to make them ASCII-safe.

        Included payloads must have been encoded using /_debug/encode_payload.

        tags: Debug
        """
        message = self.codec.encode_request(args)
        return web.json_response(
            EncodedMessage(message=message).dict()
        )


@routes.view('/_debug/decode_request')
class DecodeRequestView(CodecView):
    async def post(self, args: EncodedMessage) -> r200[IntermediateRequest]:
        """
        Decode a Request object from a base64 string.

        The base64 string is converted to bytes.
        The bytes are decoded using protobuf.

        Included payloads must be decoded using /_debug/decode_payload

        tags: Debug
        """
        request = self.codec.decode_request(args.message)
        return web.json_response(
            request.clean_dict()
        )


@routes.view('/_debug/encode_response')
class EncodeResponseView(CodecView):
    async def post(self, args: IntermediateResponse) -> r200[EncodedMessage]:
        """
        Encode a Response object to a base64 string.

        Te object encoded to protobuf bytes.
        The bytes are encoded as base64 to make them ASCII-safe.

        Included payloads must have been encoded using /_debug/encode_payload.

        tags: Debug
        """
        message = self.codec.encode_response(args)
        return web.json_response(
            EncodedMessage(message=message).dict()
        )


@routes.view('/_debug/decode_response')
class DecodeResponseView(CodecView):
    async def post(self, args: EncodedMessage) -> r200[IntermediateResponse]:
        """
        Decode a Response object from a base64 string.

        The base64 string is converted to bytes.
        The bytes are decoded using protobuf.

        Included payloads must be decoded using /_debug/decode_payload

        tags: Debug
        """
        response = self.codec.decode_response(args.message)
        return web.json_response(
            response.clean_dict()
        )


@routes.view('/_debug/encode_payload')
class EncodePayloadView(CodecView):
    async def post(self, args: DecodedPayload) -> r200[EncodedPayload]:
        """
        Encode a Payload object.

        `content` is encoded to protobuf bytes,
        and then encoded as base64 to make it ASCII-safe.

        This operation is symmetrical with /_debug/decode_payload.

        tags: Debug
        """
        payload = self.codec.encode_payload(args)
        return web.json_response(
            payload.clean_dict()
        )


@routes.view('/_debug/decode_payload')
class DecodePayloadView(CodecView):
    async def post(self, args: EncodedPayload) -> r200[DecodedPayload]:
        """
        Decode a Payload object.

        `content` is converted to bytes,
        and then decoded using protobuf.

        This operation is symmetrical with /_debug/encode_payload

        tags: Debug
        """
        payload = self.codec.decode_payload(args)
        return web.json_response(
            payload.clean_dict()
        )
