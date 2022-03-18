"""
REST API for system debugging
"""

from typing import Optional

from aiohttp import web
from aiohttp_pydantic import PydanticView
from aiohttp_pydantic.oas.typing import r200
from brewblox_service import brewblox_logger

from brewblox_devcon_spark import codec
from brewblox_devcon_spark.models import DecodeArgs, EncodeArgs

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()


def setup(app: web.Application):
    app.router.add_routes(routes)


class CodecView(PydanticView):
    def __init__(self, request: web.Request) -> None:
        super().__init__(request)
        self.codec = codec.fget(request.app)

    async def encode_payload(self, payload: Optional[dict]):
        if not payload:
            return
        blockType = payload['blockType']
        subtype = payload.get('subtype')
        content = payload['content']
        (blockType, subtype), content = await self.codec.encode((blockType, subtype), content)
        payload['blockType'] = blockType
        payload['subtype'] = subtype
        payload['content'] = content

    async def decode_payload(self, payload: Optional[dict]):
        if not payload:
            return
        blockType = payload['blockType']
        subtype = payload.get('subtype')
        content = payload['content']
        (blockType, subtype), content = await self.codec.decode((blockType, subtype), content)
        payload['blockType'] = blockType
        payload['subtype'] = subtype
        payload['content'] = content


@routes.view('/_debug/encode')
class EncodeView(CodecView):
    async def post(self, args: EncodeArgs) -> r200[DecodeArgs]:
        """
        Manually encode a protobuf message.

        Tags: Debug
        """
        if args.blockType in [codec.REQUEST_TYPE, codec.REQUEST_TYPE_INT]:
            await self.encode_payload(args.content['payload'])

        if args.blockType in [codec.RESPONSE_TYPE, codec.RESPONSE_TYPE_INT]:
            for payload in args.content.get('payload', []):
                await self.encode_payload(payload)

        (blockType, subtype), content = await self.codec.encode(
            (args.blockType, args.subtype),
            args.content
        )

        encoded = DecodeArgs(
            blockType=blockType,
            subtype=subtype,
            content=content,
        )

        return web.json_response(
            encoded.dict()
        )


@routes.view('/_debug/decode')
class DecodeView(CodecView):
    async def post(self, args: DecodeArgs) -> r200[EncodeArgs]:
        """
        Manually decode a protobuf message.

        Tags: Debug
        """
        (blockType, subtype), content = await self.codec.decode(
            (args.blockType, args.subtype),
            args.content
        )

        if blockType in [codec.REQUEST_TYPE, codec.REQUEST_TYPE_INT]:
            await self.decode_payload(content.get('payload'))

        if blockType in [codec.RESPONSE_TYPE, codec.RESPONSE_TYPE_INT]:
            for payload in content.get('payload', []):
                await self.decode_payload(payload)

        decoded = EncodeArgs(
            blockType=blockType,
            subtype=subtype,
            content=content,
        )

        return web.json_response(
            decoded.dict()
        )
