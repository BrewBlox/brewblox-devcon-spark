"""
Command-based device communication.
Requests are matched with responses here.
"""

import asyncio
from typing import Optional

from aiohttp import web
from brewblox_service import brewblox_logger, features, strex

from brewblox_devcon_spark import codec, connection, exceptions
from brewblox_devcon_spark.codec.opts import DecodeOpts
from brewblox_devcon_spark.models import (DecodedPayload, EncodedPayload,
                                          ErrorCode, FirmwareBlock,
                                          FirmwareBlockIdentity,
                                          IntermediateRequest,
                                          IntermediateResponse, Opcode)

LOGGER = brewblox_logger(__name__)


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
        self._active_messages: dict[int, asyncio.Future[IntermediateResponse]] = {}
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

    def _to_payload(self, block: FirmwareBlock, include_data=True) -> EncodedPayload:
        if block.type:
            (blockType, subtype) = codec.split_type(block.type)
            content = block.data if include_data else None
            payload = DecodedPayload(
                blockId=block.nid,
                blockType=blockType,
                subypte=subtype,
                content=content
            )
        else:
            payload = DecodedPayload(blockId=block.nid)

        return self._codec.encode_payload(payload)

    def _to_block(self, payload: EncodedPayload, opts: DecodeOpts) -> FirmwareBlock:
        payload = self._codec.decode_payload(payload, opts=opts)
        return FirmwareBlock(
            nid=payload.blockId,
            type=codec.join_type(payload.blockType, payload.subtype),
            data=payload.content,
        )

    async def _data_callback(self, msg: str):
        try:
            response = self._codec.decode_response(msg)

            # Get the Future object awaiting this request
            # the msgid field is key
            fut = self._active_messages.get(response.msgId)
            if fut is None:
                raise ValueError(f'Unexpected message, {response=}')
            fut.set_result(response)

        except Exception as ex:
            LOGGER.error(f'Error parsing message `{msg}` : {strex(ex)}')

    async def _execute(self,
                       opcode: Opcode,
                       payload: Optional[EncodedPayload],
                       ) -> list[EncodedPayload]:
        msg_id = self._next_id()

        request = IntermediateRequest(
            msgId=msg_id,
            opcode=opcode,
            payload=payload
        )

        request_msg = self._codec.encode_request(request)
        fut: asyncio.Future[IntermediateResponse] = asyncio.get_running_loop().create_future()
        self._active_messages[msg_id] = fut

        try:
            await self._conn.write(request_msg)
            response = await asyncio.wait_for(fut, timeout=self._timeout)

            if response.error != ErrorCode.OK:
                raise exceptions.CommandException(f'{opcode.name}, {response.error.name}')

            return response.payload

        except asyncio.TimeoutError:
            raise exceptions.CommandTimeout(opcode.name)

        finally:
            del self._active_messages[msg_id]

    async def start_reconnect(self):
        await self._conn.start_reconnect()

    async def validate(self, block: FirmwareBlock) -> FirmwareBlock:
        request = IntermediateRequest(
            msgId=0,
            opcode=Opcode.NONE,
            payload=self._to_payload(block),
        )
        self._codec.encode_request(request)
        return block

    async def noop(self) -> None:
        await self._execute(Opcode.NONE, None)

    async def version(self) -> None:
        await self._execute(Opcode.VERSION, None)

    async def read_block(self, ident: FirmwareBlockIdentity) -> FirmwareBlock:
        payloads = await self._execute(
            Opcode.BLOCK_READ,
            self._to_payload(ident, False),
        )
        return self._to_block(payloads[0], self.default_decode_opts)

    async def read_logged_block(self, ident: FirmwareBlockIdentity) -> FirmwareBlock:
        payloads = await self._execute(
            Opcode.BLOCK_READ,
            self._to_payload(ident, False),
        )
        return self._to_block(payloads[0], self.logged_decode_opts)

    async def read_all_blocks(self) -> list[FirmwareBlock]:
        payloads = await self._execute(
            Opcode.BLOCK_READ_ALL,
            None,
        )
        return [self._to_block(v, self.default_decode_opts)
                for v in payloads]

    async def read_all_logged_blocks(self) -> list[FirmwareBlock]:
        payloads = await self._execute(
            Opcode.BLOCK_READ_ALL,
            None,
        )
        return [self._to_block(v, self.logged_decode_opts)
                for v in payloads]

    async def read_all_broadcast_blocks(self) -> tuple[list[FirmwareBlock], list[FirmwareBlock]]:
        payloads = await self._execute(
            Opcode.BLOCK_READ_ALL,
            None,
        )
        default_retv = [self._to_block(v, self.default_decode_opts)
                        for v in payloads]
        logged_retv = [self._to_block(v, self.logged_decode_opts)
                       for v in payloads]
        return (default_retv, logged_retv)

    async def write_block(self, block: FirmwareBlock) -> FirmwareBlock:
        payloads = await self._execute(
            Opcode.BLOCK_WRITE,
            self._to_payload(block),
        )
        return self._to_block(payloads[0], self.default_decode_opts)

    async def create_block(self, block: FirmwareBlock) -> FirmwareBlock:
        payloads = await self._execute(
            Opcode.BLOCK_CREATE,
            self._to_payload(block),
        )
        return self._to_block(payloads[0], self.default_decode_opts)

    async def delete_block(self, ident: FirmwareBlockIdentity) -> None:
        await self._execute(
            Opcode.BLOCK_DELETE,
            self._to_payload(ident, False),
        )

    async def discover_blocks(self) -> list[FirmwareBlock]:
        payloads = await self._execute(
            Opcode.BLOCK_DISCOVER,
            None,
        )
        return [self._to_block(v, self.default_decode_opts)
                for v in payloads]

    async def read_stored_block(self, ident: FirmwareBlockIdentity) -> FirmwareBlock:
        payloads = await self._execute(
            Opcode.STORAGE_READ,
            self._to_payload(ident, False),
        )
        return self._to_block(payloads[0], self.stored_decode_opts)

    async def read_all_stored_blocks(self) -> list[FirmwareBlock]:
        payloads = await self._execute(
            Opcode.STORAGE_READ_ALL,
            None,
        )
        return [self._to_block(v, self.stored_decode_opts)
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
