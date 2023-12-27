"""
Command-based device communication.
Requests are matched with responses here.
"""

import asyncio
import logging
from contextvars import ContextVar

from . import codec, connection, exceptions, state_machine, utils
from .codec.opts import DecodeOpts
from .models import (ControllerDescription, DecodedPayload, DeviceDescription,
                     EncodedPayload, ErrorCode, FirmwareBlock,
                     FirmwareBlockIdentity, FirmwareDescription,
                     HandshakeMessage, IntermediateRequest,
                     IntermediateResponse, MaskMode, Opcode)

WELCOME_PREFIX = '!BREWBLOX'
HANDSHAKE_KEYS = [
    'name',
    'firmware_version',
    'proto_version',
    'firmware_date',
    'proto_date',
    'system_version',
    'platform',
    'reset_reason_hex',
    'reset_data_hex',
    'device_id',
]

LOGGER = logging.getLogger(__name__)
CV: ContextVar['SparkCommander'] = ContextVar('commander.SparkCommander')


class SparkCommander:

    default_decode_opts = codec.DecodeOpts()
    stored_decode_opts = codec.DecodeOpts(enums=codec.ProtoEnumOpt.INT)
    logged_decode_opts = codec.DecodeOpts(enums=codec.ProtoEnumOpt.INT,
                                          filter=codec.FilterOpt.LOGGED,
                                          metadata=codec.MetadataOpt.POSTFIX,
                                          dates=codec.DateFormatOpt.SECONDS)

    def __init__(self):
        self.config = utils.get_config()
        self.codec = codec.CV.get()
        self.conn = connection.CV.get()

        self._msgid = 0
        self._active_messages: dict[int, asyncio.Future[IntermediateResponse]] = {}
        self._empty_ev = asyncio.Event()
        self._empty_ev.set()

        self.conn.on_event = self._on_event
        self.conn.on_response = self._on_response

    def __str__(self):
        return f'<{type(self).__name__} for {self.conn}>'

    def _next_id(self):
        self._msgid = (self._msgid + 1) % 0xFFFF
        return self._msgid

    def _to_payload(self,
                    block: FirmwareBlock, /,
                    identity_only=False,
                    patch=False
                    ) -> EncodedPayload:
        if block.type:
            (blockType, subtype) = codec.split_type(block.type)
            payload = DecodedPayload(
                blockId=block.nid,
                blockType=blockType,
                subypte=subtype,
                content=(None if identity_only else block.data),
                maskMode=(MaskMode.INCLUSIVE if patch else MaskMode.NO_MASK),
            )
        else:
            payload = DecodedPayload(blockId=block.nid)

        return self.codec.encode_payload(payload)

    def _to_block(self, payload: EncodedPayload, opts: DecodeOpts) -> FirmwareBlock:
        payload = self.codec.decode_payload(payload, opts=opts)
        return FirmwareBlock(
            nid=payload.blockId,
            type=codec.join_type(payload.blockType, payload.subtype),
            data=payload.content or {},
        )

    async def _on_event(self, msg: str):
        if msg.startswith(WELCOME_PREFIX):
            handshake_values = msg.removeprefix('!').split(',')
            handshake = HandshakeMessage(**dict(zip(HANDSHAKE_KEYS, handshake_values)))
            LOGGER.info(handshake)

            desc = ControllerDescription(
                system_version=handshake.system_version,
                platform=handshake.platform,
                reset_reason=handshake.reset_reason,
                firmware=FirmwareDescription(
                    firmware_version=handshake.firmware_version,
                    proto_version=handshake.proto_version,
                    firmware_date=handshake.firmware_date,
                    proto_date=handshake.proto_date,
                ),
                device=DeviceDescription(
                    device_id=handshake.device_id,
                ),
            )
            state_machine.CV.get().set_acknowledged(desc)

        else:
            LOGGER.info(f'Spark log: `{msg}`')

    async def _on_response(self, msg: str):
        try:
            LOGGER.trace(f'response: {msg}')
            response = self.codec.decode_response(msg)

            # Get the Future object awaiting this request
            # the msgid field is key
            fut = self._active_messages.get(response.msgId)
            if fut is None:
                raise ValueError(f'Unexpected message, {response=}')
            fut.set_result(response)

        except Exception as ex:
            LOGGER.error(f'Error parsing message `{msg}` : {utils.strex(ex)}')

    async def _execute(self,
                       opcode: Opcode,
                       payload: EncodedPayload | None,
                       ) -> list[EncodedPayload]:
        msg_id = self._next_id()

        request = IntermediateRequest(
            msgId=msg_id,
            opcode=opcode,
            payload=payload
        )

        msg = self.codec.encode_request(request)
        fut: asyncio.Future[IntermediateResponse] = asyncio.get_running_loop().create_future()
        self._active_messages[msg_id] = fut
        self._empty_ev.clear()

        try:
            LOGGER.trace(f'request: {msg}')
            await self.conn.send_request(msg)
            response = await asyncio.wait_for(fut,
                                              timeout=self.config.command_timeout.total_seconds())

            if response.error != ErrorCode.OK:
                raise exceptions.CommandException(f'{opcode.name}, {response.error.name}')

            return response.payload

        except asyncio.TimeoutError:
            raise exceptions.CommandTimeout(opcode.name)

        finally:
            del self._active_messages[msg_id]
            if not self._active_messages:
                self._empty_ev.set()

    async def validate(self, block: FirmwareBlock) -> FirmwareBlock:
        request = IntermediateRequest(
            msgId=0,
            opcode=Opcode.NONE,
            payload=self._to_payload(block),
        )
        self.codec.encode_request(request)
        return block

    async def noop(self) -> None:
        await self._execute(Opcode.NONE, None)

    async def version(self) -> None:
        await self._execute(Opcode.VERSION, None)

    async def read_block(self, ident: FirmwareBlockIdentity) -> FirmwareBlock:
        payloads = await self._execute(
            Opcode.BLOCK_READ,
            self._to_payload(ident, identity_only=True),
        )
        return self._to_block(payloads[0], self.default_decode_opts)

    async def read_logged_block(self, ident: FirmwareBlockIdentity) -> FirmwareBlock:
        payloads = await self._execute(
            Opcode.BLOCK_READ,
            self._to_payload(ident, identity_only=True),
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

    async def patch_block(self, block: FirmwareBlock) -> FirmwareBlock:
        payloads = await self._execute(
            Opcode.BLOCK_WRITE,
            self._to_payload(block, patch=True),
        )
        return self._to_block(payloads[0], self.default_decode_opts)

    async def create_block(self, block: FirmwareBlock) -> FirmwareBlock:
        payloads = await self._execute(
            Opcode.BLOCK_CREATE,
            self._to_payload(block, patch=True),
        )
        return self._to_block(payloads[0], self.default_decode_opts)

    async def delete_block(self, ident: FirmwareBlockIdentity) -> None:
        await self._execute(
            Opcode.BLOCK_DELETE,
            self._to_payload(ident, identity_only=True),
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
            Opcode.BLOCK_STORED_READ,
            self._to_payload(ident, identity_only=True),
        )
        return self._to_block(payloads[0], self.stored_decode_opts)

    async def read_all_stored_blocks(self) -> list[FirmwareBlock]:
        payloads = await self._execute(
            Opcode.BLOCK_STORED_READ_ALL,
            None,
        )
        return [self._to_block(v, self.stored_decode_opts)
                for v in payloads]

    async def reboot(self) -> None:
        await self._execute(
            Opcode.REBOOT,
            None,
        )

    async def clear_blocks(self) -> list[FirmwareBlock]:
        payloads = await self._execute(
            Opcode.CLEAR_BLOCKS,
            None,
        )
        return [self._to_block(v, self.default_decode_opts)
                for v in payloads]

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

    async def reset_connection(self) -> None:
        await self.conn.reset()

    async def end_connection(self) -> None:
        await self.conn.end()

    async def wait_empty(self) -> None:
        await self._empty_ev.wait()


def setup():
    CV.set(SparkCommander())
