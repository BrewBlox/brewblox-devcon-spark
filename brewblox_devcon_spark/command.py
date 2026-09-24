"""
Command-based device communication.
Requests are matched with responses here.
"""

import asyncio
import logging
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import timedelta

from . import codec, connection, exceptions, state_machine, utils
from .models import (
    ControllerDescription,
    DecodedPayload,
    DeviceDescription,
    EncodedPayload,
    ErrorCode,
    FirmwareBlock,
    FirmwareBlockIdentity,
    FirmwareDescription,
    HandshakeMessage,
    IntermediateRequest,
    IntermediateResponse,
    Opcode,
    ReadMode,
)

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

# The controller emits a handshake as part of its reply to these opcodes.
# A handshake answering one of these is solicited, and must not be
# mistaken for the start of a new session.
HANDSHAKE_OPCODES = frozenset({Opcode.NONE, Opcode.VERSION})

LOGGER = logging.getLogger(__name__)
CV: ContextVar['CboxCommander'] = ContextVar('command.CboxCommander')


@dataclass(frozen=True)
class BlockChange:
    """
    The outcome of a request that changes blocks or reads them all,
    or a sign that blocks changed where no response shows it.
    Sent to the block listener (`CboxCommander.on_block_change`).
    """

    seq: int
    """The send order of the request. Responses may be handled out of order."""

    session: int
    """The state machine session when the request was sent."""

    opcode: Opcode | None
    """None if no request shows the change: a late response, or a controller reboot."""

    mode: ReadMode = ReadMode.DEFAULT

    blocks: list[FirmwareBlock] = field(default_factory=list)
    """The decoded response payloads, also those that came with an error."""

    nid: int | None = None
    """The block ID in the request, if any."""

    error: str | None = None
    """None if the request succeeded. Otherwise the error response, or why no response came."""


class CboxCommander:
    def __init__(self):
        self.config = utils.get_config()
        self.state = state_machine.CV.get()
        self.codec = codec.CV.get()
        self.conn = connection.CV.get()

        self._msgid = 0
        self._seq = 0
        self._active_messages: dict[int, asyncio.Future[IntermediateResponse]] = {}
        self._handshake_msgids: set[int] = set()
        self._empty_ev = asyncio.Event()
        self._empty_ev.set()

        self.conn.on_event = self._on_event
        self.conn.on_response = self._on_response

        self.on_block_change: Callable[[BlockChange], None] | None = None

    def _next_id(self):
        self._msgid = (self._msgid + 1) % 0xFFFF
        return self._msgid

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def _notify(self, change: BlockChange):
        if self.on_block_change is None:
            return
        try:
            self.on_block_change(change)
        except Exception as ex:
            LOGGER.error(
                f'Block listener failed on {change.opcode} (seq={change.seq}): {utils.strex(ex)}', exc_info=True
            )

    def _to_payload(
        self,
        block: FirmwareBlock,
        /,
        identity_only=False,
    ) -> EncodedPayload:
        if block.type:
            payload = DecodedPayload(
                blockId=block.nid,
                blockType=block.type,
                name=block.id,
                content=(None if identity_only else block.data),
            )
        else:
            payload = DecodedPayload(blockId=block.nid, name=block.id)

        return self.codec.encode_payload(payload)

    def _to_block(
        self,
        payload: EncodedPayload,
        /,
        mode: ReadMode = ReadMode.DEFAULT,
    ) -> FirmwareBlock:
        payload = self.codec.decode_payload(payload, mode=mode)
        return FirmwareBlock(
            id=payload.name,
            nid=payload.blockId,
            type=payload.blockType,
            data=payload.content or {},
        )

    def _reset_active_messages(self, reason: str):
        """
        Cancel in-flight command Futures with the given reason.
        Used when the stream is known to be desynced or a fresh session starts,
        so waiting callers fail fast instead of hitting command_timeout.

        Commands that solicit a handshake are skipped: their own reply
        is what triggered the reset, and is still on its way.
        """
        stale = [msg_id for msg_id in self._active_messages if msg_id not in self._handshake_msgids]
        if not stale:
            return

        ex = exceptions.ConnectionException(reason)
        for msg_id in stale:
            fut = self._active_messages.pop(msg_id)
            if not fut.done():
                fut.set_exception(ex)

        if not self._active_messages:
            self._empty_ev.set()

    async def _on_event(self, msg: str):
        if msg.startswith(WELCOME_PREFIX):
            # The controller sends a handshake on connect, and in reply to NONE/VERSION.
            # Only the first handshake of a session is a transport-level sync marker:
            # anything buffered before it was boot or reconnect noise.
            if not self.state.is_acknowledged():
                self.conn.reset_stream()
                self._reset_active_messages('handshake received; prior session discarded')
            elif not self._handshake_msgids:
                # Not solicited by NONE/VERSION: the controller rebooted, and blocks may have changed
                self._notify(BlockChange(self._seq, self.state.session, None, error='unsolicited handshake'))

            handshake_values = msg.removeprefix('!').split(',')
            handshake = HandshakeMessage(**dict(zip(HANDSHAKE_KEYS, handshake_values, strict=False)))
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
            self.state.set_acknowledged(desc)

        else:
            LOGGER.info(f'Firmware log: `{msg}`')

    async def _on_response(self, msg: str):
        try:
            LOGGER.trace(f'response: {msg}')
            response = self.codec.decode_response(msg)
        except Exception as ex:
            # Pre-handshake: early boot / bootloader bytes may arrive unframed
            # and fail to decode. Quietly drop.
            if not self.state.is_acknowledged():
                LOGGER.debug(f'Ignoring pre-handshake message `{msg}`: {utils.strex(ex)}')
                return

            # Post-handshake: decode failure means the stream is desynced.
            # Should be rare with atomic framed writes; loud when it happens.
            # Fail any in-flight commands fast instead of waiting command_timeout.
            if self._active_messages:
                LOGGER.warning(
                    f'Decode error, failing {len(self._active_messages)} in-flight command(s): {utils.strex(ex)}'
                )
                self._reset_active_messages(f'Decode error on incoming response: {utils.strex(ex)}')
            else:
                LOGGER.warning(f'Decode error on unsolicited message `{msg}`: {utils.strex(ex)}')
            return

        fut = self._active_messages.get(response.msgId)
        if fut is None:
            # Decoded cleanly but no caller waiting: stray/duplicate/post-timeout.
            # Rare — log visibly so we notice if it stops being rare.
            LOGGER.warning(f'Unexpected message, {response=}')
            # A request that timed out or was cancelled may still have changed blocks
            self._notify(BlockChange(self._seq, self.state.session, None, error='late response'))
            return
        fut.set_result(response)

    async def _send(
        self,
        opcode: Opcode,
        payload: EncodedPayload | None,
        mode: ReadMode,
        timeout: timedelta | None,
    ) -> IntermediateResponse:
        """
        Sends a request, and waits for its response.
        An error response is returned, not raised.

        Nothing between the call and the write to the transport yields to the event loop:
        a send sequence number assigned just before the call is the order on the wire.
        """
        msg_id = self._next_id()

        request = IntermediateRequest(msgId=msg_id, opcode=opcode, mode=mode, payload=payload)

        msg = self.codec.encode_request(request)
        fut: asyncio.Future[IntermediateResponse] = asyncio.get_running_loop().create_future()
        self._active_messages[msg_id] = fut
        if opcode in HANDSHAKE_OPCODES:
            self._handshake_msgids.add(msg_id)
        self._empty_ev.clear()

        try:
            LOGGER.trace(f'request: {msg}')
            await self.conn.send_request(msg)
            return await asyncio.wait_for(fut, timeout=(timeout or self.config.command_timeout).total_seconds())

        except TimeoutError:
            raise exceptions.CommandTimeout(opcode.name)

        finally:
            # _reset_active_messages() may have already cleared this entry
            # if the session was reset while we were waiting.
            self._active_messages.pop(msg_id, None)
            self._handshake_msgids.discard(msg_id)
            if not self._active_messages:
                self._empty_ev.set()

    async def _execute(
        self,
        opcode: Opcode,
        /,
        payload: EncodedPayload | None = None,
        mode: ReadMode = ReadMode.DEFAULT,
        timeout: timedelta | None = None,
    ) -> list[EncodedPayload]:
        """
        Sends a request, and returns the payloads of its response.
        `timeout` defaults to the `command_timeout` setting.
        """
        self._next_seq()
        response = await self._send(opcode, payload, mode, timeout)

        if response.error != ErrorCode.OK:
            raise exceptions.CommandException(f'{opcode.name}, {response.error.name}')

        return response.payload

    async def _execute_blocks(
        self,
        opcode: Opcode,
        /,
        payload: EncodedPayload | None = None,
        mode: ReadMode = ReadMode.DEFAULT,
        timeout: timedelta | None = None,
    ) -> list[FirmwareBlock]:
        """
        Sends a request that changes blocks or reads them all, and returns the decoded blocks.
        The block listener is notified of the outcome: the decoded blocks,
        also those that came with an error response, or why the request failed.
        Errors are raised after notifying.
        """
        nid = payload.blockId if payload else None
        session = self.state.session
        seq = self._next_seq()

        try:
            response = await self._send(opcode, payload, mode, timeout)
        except Exception as ex:
            self._notify(BlockChange(seq, session, opcode, mode, nid=nid, error=utils.strex(ex)))
            raise

        blocks = [self._to_block(v, mode=mode) for v in response.payload]
        error = None if response.error == ErrorCode.OK else response.error.name
        self._notify(BlockChange(seq, session, opcode, mode, blocks, nid, error))

        if error:
            raise exceptions.CommandException(f'{opcode.name}, {error}')

        return blocks

    async def validate(self, block: FirmwareBlock) -> FirmwareBlock:
        request = IntermediateRequest(
            msgId=0,
            opcode=Opcode.NONE,
            mode=ReadMode.DEFAULT,
            payload=self._to_payload(block),
        )
        self.codec.encode_request(request)
        return block

    async def noop(self) -> None:
        await self._execute(Opcode.NONE)

    async def version(self) -> None:
        await self._execute(Opcode.VERSION)

    async def read_block(self, ident: FirmwareBlockIdentity, mode: ReadMode = ReadMode.DEFAULT) -> FirmwareBlock:
        payloads = await self._execute(
            Opcode.BLOCK_READ, mode=mode, payload=self._to_payload(ident, identity_only=True)
        )
        return self._to_block(payloads[0], mode=mode)

    async def read_all_blocks(
        self,
        mode: ReadMode = ReadMode.DEFAULT,
        *,
        timeout: timedelta | None = None,
    ) -> list[FirmwareBlock]:
        """
        Reads all blocks.
        A CHANGED read only returns the blocks whose readonly state changed
        since the previous CHANGED read on this connection, without their names.
        """
        return await self._execute_blocks(Opcode.BLOCK_READ_ALL, mode=mode, timeout=timeout)

    async def write_block(self, block: FirmwareBlock) -> FirmwareBlock:
        """
        Writes the fields present in the block data. Absent fields keep their value.
        Returns the block as it is after writing.
        """
        blocks = await self._execute_blocks(Opcode.BLOCK_WRITE, payload=self._to_payload(block))
        return blocks[0]

    async def patch_block(self, block: FirmwareBlock) -> FirmwareBlock:
        # Writes are by presence: every write is a patch
        return await self.write_block(block)

    async def create_block(self, block: FirmwareBlock) -> FirmwareBlock:
        blocks = await self._execute_blocks(Opcode.BLOCK_CREATE, payload=self._to_payload(block))
        return blocks[0]

    async def delete_block(self, ident: FirmwareBlockIdentity) -> None:
        await self._execute_blocks(Opcode.BLOCK_DELETE, payload=self._to_payload(ident, identity_only=True))

    async def discover_blocks(self) -> list[FirmwareBlock]:
        return await self._execute_blocks(Opcode.BLOCK_DISCOVER)

    async def read_all_block_names(self) -> list[FirmwareBlock]:
        payloads = await self._execute(Opcode.NAME_READ_ALL)
        return [self._to_block(v) for v in payloads]

    async def write_block_name(self, ident: FirmwareBlockIdentity) -> FirmwareBlock:
        payloads = await self._execute(Opcode.NAME_WRITE, payload=self._to_payload(ident, identity_only=True))
        return self._to_block(payloads[0])

    async def reboot(self) -> None:
        await self._execute(Opcode.REBOOT)

    async def clear_blocks(self) -> list[FirmwareBlock]:
        return await self._execute_blocks(Opcode.CLEAR_BLOCKS)

    async def clear_wifi(self) -> None:
        await self._execute(Opcode.CLEAR_WIFI)

    async def factory_reset(self) -> None:
        await self._execute(Opcode.FACTORY_RESET)

    async def firmware_update(self) -> None:
        await self._execute(Opcode.FIRMWARE_UPDATE)

    async def reset_connection(self) -> None:
        await self.conn.reset()

    async def end_connection(self) -> None:
        await self.conn.end()

    async def wait_empty(self) -> None:
        await self._empty_ev.wait()


def setup():
    CV.set(CboxCommander())
