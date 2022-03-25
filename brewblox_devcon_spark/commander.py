"""
Command-based device communication.
Requests are matched with responses here.
"""

import asyncio
from typing import Optional

from aiohttp import web
from brewblox_service import brewblox_logger, features, strex

from brewblox_devcon_spark import codec, connection, exceptions
from brewblox_devcon_spark.models import (EncodedPayload, EncodedRequest,
                                          EncodedResponse, ErrorCode,
                                          FirmwareBlock, FirmwareBlockIdentity,
                                          Opcode)

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


class SparkCommander(features.ServiceFeature):

    default_decode_opts = codec.DecodeOpts()
    stored_decode_opts = codec.DecodeOpts(enums=codec.ProtoEnumOpt.INT)
    logged_decode_opts = codec.DecodeOpts(enums=codec.ProtoEnumOpt.INT,
                                          filter=codec.FilterOpt.LOGGED,
                                          metadata=codec.MetadataOpt.POSTFIX)

    def __init__(self, app: web.Application):
        super().__init__(app)

        self._msgid = 0
        self._timeout = app['config']['command_timeout']
        self._active_messages: dict[int, asyncio.Future] = {}
        self._codec = codec.fget(app)
        self._conn = connection.fget(app)

    def __str__(self):
        return f'<{type(self).__name__} for {self._conn}>'

    async def startup(self, app: web.Application):
        self._active_messages.clear()
        self._conn.data_callbacks.add(self._data_callback)

    async def shutdown(self, app: web.Application):
        self._conn.data_callbacks.discard(self._data_callback)

    def _next_id(self):
        self._msgid = (self._msgid + 1) % 0xFFFF
        return self._msgid

    async def _to_payload(self, block: FirmwareBlock, include_data=True) -> EncodedPayload:
        if block.type:
            (blockType, subtype) = split_type(block.type)
            data = block.data if include_data else None
            (blockType, subtype), content = await self._codec.encode((blockType, subtype), data)
            return EncodedPayload(
                blockId=block.nid,
                blockType=blockType,
                subtype=subtype,
                content=content,
            )
        else:
            return EncodedPayload(
                blockId=block.nid
            )

    async def _to_block(self,
                        payload: EncodedPayload,
                        opts: codec.DecodeOpts,
                        ) -> FirmwareBlock:
        enc_id = (payload.blockType, payload.subtype)
        enc_content = payload.content
        (blockType, subtype), data = await self._codec.decode(enc_id, enc_content, opts)
        return FirmwareBlock(
            nid=payload.blockId,
            type=join_type(blockType, subtype),
            data=data,
        )

    async def _data_callback(self, msg: str):
        try:
            _, dec_data = await self._codec.decode(
                (codec.RESPONSE_TYPE, None),
                msg,
            )
            response = EncodedResponse(**dec_data)

            # Get the Future object awaiting this request
            # the msgid field is key
            fut = self._active_messages.get(response.msgId)
            if fut is None:
                raise ValueError(f'Unexpected message {response}')
            fut.set_result(response)

        except Exception as ex:
            LOGGER.error(f'Error parsing message `{msg}` : {strex(ex)}')

    async def _execute(self,
                       opcode: Opcode,
                       payload: Optional[EncodedPayload],
                       /,
                       ) -> list[EncodedPayload]:
        msg_id = self._next_id()

        request = EncodedRequest(
            msgId=msg_id,
            opcode=opcode,
            payload=payload
        )

        _, request_data = await self._codec.encode((codec.REQUEST_TYPE, None), request.dict())
        fut: asyncio.Future[EncodedResponse] = asyncio.get_running_loop().create_future()
        self._active_messages[msg_id] = fut

        try:
            await self._conn.write(request_data)
            enc_response = await asyncio.wait_for(fut, timeout=self._timeout)

            if enc_response.error != ErrorCode.OK:
                raise exceptions.CommandException(f'{opcode.name}, {enc_response.error.name}')

            return enc_response.payload

        except asyncio.TimeoutError:
            raise exceptions.CommandTimeout(opcode.name)

        finally:
            del self._active_messages[msg_id]

    async def start_reconnect(self):
        await self._conn.start_reconnect()

    async def validate(self, block: FirmwareBlock) -> FirmwareBlock:
        request = EncodedRequest(
            msgId=0,
            opcode=Opcode.NONE,
            payload=await self._to_payload(block)
        )
        await self._codec.encode((codec.REQUEST_TYPE, None), request.dict())
        return block

    async def noop(self) -> None:
        await self._execute(Opcode.NONE, None)

    async def version(self) -> None:
        await self._execute(Opcode.VERSION, None)

    async def read_block(self, ident: FirmwareBlockIdentity) -> FirmwareBlock:
        payloads = await self._execute(
            Opcode.BLOCK_READ,
            await self._to_payload(ident, False),
        )
        return await self._to_block(payloads[0], self.default_decode_opts)

    async def read_logged_block(self, ident: FirmwareBlockIdentity) -> FirmwareBlock:
        payloads = await self._execute(
            Opcode.BLOCK_READ,
            await self._to_payload(ident, False),
        )
        return await self._to_block(payloads[0], self.logged_decode_opts)

    async def read_all_blocks(self) -> list[FirmwareBlock]:
        payloads = await self._execute(
            Opcode.BLOCK_READ_ALL,
            None,
        )
        return [await self._to_block(v, self.default_decode_opts)
                for v in payloads]

    async def read_all_logged_blocks(self) -> list[FirmwareBlock]:
        payloads = await self._execute(
            Opcode.BLOCK_READ_ALL,
            None,
        )
        return [await self._to_block(v, self.logged_decode_opts)
                for v in payloads]

    async def read_all_broadcast_blocks(self) -> tuple[list[FirmwareBlock], list[FirmwareBlock]]:
        payloads = await self._execute(
            Opcode.BLOCK_READ_ALL,
            None,
        )
        default_retv = [await self._to_block(v, self.default_decode_opts)
                        for v in payloads]
        logged_retv = [await self._to_block(v, self.logged_decode_opts)
                       for v in payloads]
        return (default_retv, logged_retv)

    async def write_block(self, block: FirmwareBlock) -> FirmwareBlock:
        payloads = await self._execute(
            Opcode.BLOCK_WRITE,
            await self._to_payload(block),
        )
        return await self._to_block(payloads[0], self.default_decode_opts)

    async def create_block(self, block: FirmwareBlock) -> FirmwareBlock:
        payloads = await self._execute(
            Opcode.BLOCK_CREATE,
            await self._to_payload(block),
        )
        return await self._to_block(payloads[0], self.default_decode_opts)

    async def delete_block(self, ident: FirmwareBlockIdentity) -> None:
        await self._execute(
            Opcode.BLOCK_DELETE,
            await self._to_payload(ident, False),
        )

    async def discover_blocks(self) -> list[FirmwareBlock]:
        payloads = await self._execute(
            Opcode.BLOCK_DISCOVER,
            None,
        )
        return [await self._to_block(v, self.default_decode_opts)
                for v in payloads]

    async def read_stored_block(self, ident: FirmwareBlockIdentity) -> FirmwareBlock:
        payloads = await self._execute(
            Opcode.STORAGE_READ,
            await self._to_payload(ident, False),
        )
        return await self._to_block(payloads[0], self.stored_decode_opts)

    async def read_all_stored_blocks(self) -> list[FirmwareBlock]:
        payloads = await self._execute(
            Opcode.STORAGE_READ_ALL,
            None,
        )
        return [await self._to_block(v, self.stored_decode_opts)
                for v in payloads]

    async def reboot(self) -> None:
        await self._execute(
            Opcode.REBOOT,
            None,
        )

    async def clear_blocks(self) -> None:
        await self._execute(
            Opcode.CLEAR_BLOCKS,
            None,
        )

    async def clear_wifi(self) -> None:
        await self._execute(
            Opcode.CLEAR_WIFI,
            None,
        )

    async def factory_reset(self) -> None:
        await self._execute(
            Opcode.FACTORY_RESET,
            None,
        )

    async def firmware_update(self) -> None:
        await self._execute(
            Opcode.FIRMWARE_UPDATE,
            None,
        )


def setup(app: web.Application):
    features.add(app, SparkCommander(app))


def fget(app: web.Application) -> SparkCommander:
    return features.get(app, SparkCommander)
