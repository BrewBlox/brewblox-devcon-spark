"""
An in-process firmware simulation.
This is not intended to simulate firmware processes,
only to provide encoded responses that make some sense.

MockConnection is an alternative to StreamConnection or MqttConnection.
This prevents having to spin up a simulator in a separate process for tests.
"""

import logging
from base64 import b64decode, b64encode
from dataclasses import dataclass
from datetime import datetime
from itertools import count

from google.protobuf.descriptor import FieldDescriptor
from google.protobuf.message import Message

from .. import codec, const, utils
from ..codec import descriptors, lookup
from ..models import (
    CrossPlatformResetReason,
    DecodedPayload,
    EncodedPayload,
    ErrorCode,
    FirmwareBlock,
    IntermediateRequest,
    IntermediateResponse,
    Opcode,
    ReadMode,
    ResetData,
)
from .connection_impl import ConnectionCallbacks, ConnectionImplBase

LOGGER = logging.getLogger(__name__)

# an ErrorCode will be returned
# a None value will cause no response to be returned
NEXT_ERROR: list[ErrorCode | None] = []


@dataclass
class MockBlock:
    name: str
    type_int: int
    message: Message


def _is_unset(entry: Message) -> bool:
    """A map value without a member, or with `empty` set: the firmware erases it (VarContainer)"""
    return [f.name for f, _ in entry.ListFields()] in ([], ['empty'])


def erase_unset(message: Message) -> None:
    """
    Erases the unset values of the map wrappers in `message`, as the firmware does after every write.
    The Variables map is the only map wrapper.
    """
    for field, value in message.ListFields():
        if (items := descriptors.list_wrapper(field)) and descriptors.is_map(items):
            entries = getattr(value, items.name)
            for key in [k for k, v in entries.items() if _is_unset(v)]:
                del entries[key]


def merge_present(dest: Message, src: Message):
    """
    Writes by presence, as the firmware does: fields present in `src` are written, and absent fields are kept.
    Repeated fields and list wrappers are replaced whole, and singular messages are merged.
    A map wrapper (Variables) is merged by key: the keys in `src` replace their entries,
    an unset or `empty` entry deletes its key, and the other keys are kept.
    """
    for field, value in src.ListFields():
        if field.label == FieldDescriptor.LABEL_REPEATED:
            dest.ClearField(field.name)
            getattr(dest, field.name).MergeFrom(value)
        elif field.message_type is None:
            setattr(dest, field.name, value)
        elif items := descriptors.list_wrapper(field):
            if descriptors.is_map(items):
                wrapper = getattr(dest, field.name)
                wrapper.SetInParent()
                for key, entry in getattr(value, items.name).items():
                    getattr(wrapper, items.name)[key].CopyFrom(entry)
                erase_unset(dest)
            else:
                getattr(dest, field.name).CopyFrom(value)
        else:
            getattr(dest, field.name).SetInParent()
            merge_present(getattr(dest, field.name), value)


def default_blocks() -> dict[int, FirmwareBlock]:
    return {
        block.nid: block
        for block in [
            FirmwareBlock(
                id='SystemInfo',
                nid=const.SYS_BLOCK_IDS['SysInfo'],
                type='SysInfo',
                data={
                    'deviceId': 'FACADE',
                    'timeZone': 'Africa/Casablanca',
                    'updatesPerSecond': 9001,
                },
            ),
            FirmwareBlock(
                id='WiFiSettings',
                nid=const.SYS_BLOCK_IDS['WiFiSettings'],
                type='WiFiSettings',
                data={},
            ),
            FirmwareBlock(
                id='DisplaySettings',
                nid=const.SYS_BLOCK_IDS['DisplaySettings'],
                type='DisplaySettings',
                data={},
            ),
            FirmwareBlock(
                id='SparkPins',
                nid=const.SYS_BLOCK_IDS['SparkPins'],
                type='Spark3Pins',
                data={
                    'channels': [
                        {'id': 1},
                        {'id': 2},
                        {'id': 3},
                        {'id': 4},
                        {'id': 5},
                    ]
                },
            ),
        ]
    }


class MockConnection(ConnectionImplBase):
    def __init__(
        self,
        device_id: str,
        callbacks: ConnectionCallbacks,
    ) -> None:
        super().__init__('MOCK', device_id, callbacks)

        self._start_time = datetime.now()
        self._codec = codec.Codec(filter_values=False)
        self._id_counter = count(start=const.USER_NID_START)
        self._blocks: dict[int, MockBlock] = self._default_blocks()

        # Per nid, the content sent by the previous CHANGED read-all
        self._changed_sent: dict[int, bytes] = {}

    def _parse(self, payload: EncodedPayload) -> MockBlock:
        impl = next(v for v in lookup.CV_OBJECTS.get() if payload.blockType in [v.type_str, v.type_int])
        message = impl.message_cls()
        message.ParseFromString(b64decode(payload.content))
        return MockBlock(payload.name, impl.type_int, message)

    def _default_blocks(self) -> dict[int, MockBlock]:
        return {
            block.nid: self._parse(
                self._codec.encode_payload(
                    DecodedPayload(blockId=block.nid, blockType=block.type, name=block.id, content=block.data)
                )
            )
            for block in default_blocks().values()
        }

    def _to_payload(self, nid: int, block: MockBlock, name: str | None) -> EncodedPayload:
        return EncodedPayload(
            blockId=nid,
            blockType=block.type_int,
            name=name,
            content=b64encode(block.message.SerializeToString()).decode(),
        )

    def _read_changed(self) -> list[EncodedPayload]:
        """
        A CHANGED read-all: every block whose content changed since the previous CHANGED read-all, without a name.
        The firmware only sends the fields that CHANGED reads cover. A complete block is a valid superset.
        """
        payloads = []
        for nid, block in self._blocks.items():
            content = block.message.SerializeToString()
            if self._changed_sent.get(nid) != content:
                self._changed_sent[nid] = content
                payloads.append(self._to_payload(nid, block, None))
        return payloads

    def update_systime(self):
        # Uptime is skip_changed: merging a CHANGED read ignores it.
        # The system time is left to time sync, so that SysInfo does not change in the cache with every request.
        elapsed = datetime.now() - self._start_time
        self._blocks[const.SYS_BLOCK_IDS['SysInfo']].message.uptime = int(elapsed.total_seconds() * 1000)

    async def welcome(self):
        config = utils.get_config()
        fw_config = utils.get_fw_config()
        welcome = [
            '!BREWBLOX',
            fw_config.firmware_version,
            fw_config.proto_version,
            fw_config.firmware_date,
            fw_config.proto_date,
            fw_config.system_version,
            'mock',
            f'{CrossPlatformResetReason.UNKNOWN.value:02x}',
            ResetData.NOT_SPECIFIED.value,
            config.device_id,
        ]
        await self.on_event(','.join(welcome))

    async def handle_command(self, request: IntermediateRequest) -> IntermediateResponse | None:  # pragma: no cover
        response = IntermediateResponse(
            msgId=request.msgId,
            error=ErrorCode.OK,
            mode=request.mode,
            payload=[],
        )

        if NEXT_ERROR:
            error = NEXT_ERROR.pop(0)
            if error is None:
                return None  # No response at all
            response.error = error

        elif request.opcode in [
            Opcode.NONE,
            Opcode.VERSION,
        ]:
            await self.welcome()

        elif request.opcode in [
            Opcode.BLOCK_READ,
            Opcode.STORAGE_READ,
            Opcode.NAME_READ,
        ]:
            nid = request.payload.blockId
            block = self._blocks.get(nid)
            if not block:
                response.error = ErrorCode.INVALID_BLOCK_ID
            else:
                response.payload = [self._to_payload(nid, block, block.name)]

        elif request.opcode == Opcode.BLOCK_READ_ALL and request.mode == ReadMode.CHANGED:
            response.payload = self._read_changed()

        elif request.opcode in [
            Opcode.BLOCK_READ_ALL,
            Opcode.STORAGE_READ_ALL,
            Opcode.NAME_READ_ALL,
        ]:
            response.payload = [self._to_payload(nid, block, block.name) for nid, block in self._blocks.items()]

        elif request.opcode == Opcode.BLOCK_WRITE:
            nid = request.payload.blockId
            block = self._blocks.get(nid)
            if not block:
                response.error = ErrorCode.INVALID_BLOCK_ID
            else:
                src = self._parse(request.payload)
                if src.type_int != block.type_int:
                    response.error = ErrorCode.INVALID_BLOCK_TYPE
                else:
                    merge_present(block.message, src.message)
                    response.payload = [self._to_payload(nid, block, block.name)]

        elif request.opcode == Opcode.BLOCK_CREATE:
            nid = request.payload.blockId
            if nid in self._blocks or (nid > 0 and nid < const.USER_NID_START):
                response.error = ErrorCode.BLOCK_NOT_CREATABLE
            else:
                nid = nid or next(self._id_counter)
                block = self._parse(request.payload)
                erase_unset(block.message)
                self._blocks[nid] = block
                response.payload = [self._to_payload(nid, block, block.name)]

        elif request.opcode == Opcode.BLOCK_DELETE:
            nid = request.payload.blockId
            block = self._blocks.get(nid)
            if not block:
                response.error = ErrorCode.INVALID_BLOCK_ID
            elif nid < const.USER_NID_START:
                response.error = ErrorCode.BLOCK_NOT_DELETABLE
            else:
                del self._blocks[nid]
                self._changed_sent.pop(nid, None)

        elif request.opcode == Opcode.BLOCK_DISCOVER:
            # Always return spark pins when discovering blocks
            nid = const.SYS_BLOCK_IDS['SparkPins']
            block = self._blocks[nid]
            response.payload = [self._to_payload(nid, block, block.name)]

        elif request.opcode == Opcode.NAME_WRITE:
            nid = request.payload.blockId
            name = request.payload.name
            block = self._blocks.get(nid)
            match = next((v for v in self._blocks.values() if v.name == name), None)
            if not block:
                response.error = ErrorCode.INVALID_BLOCK_ID
            elif not name or (match and match is not block):
                response.error = ErrorCode.INVALID_BLOCK_NAME
            else:
                block.name = name
                response.payload = [self._to_payload(nid, block, block.name)]

        elif request.opcode == Opcode.REBOOT:
            self._start_time = datetime.now()
            self.update_systime()

        elif request.opcode == Opcode.CLEAR_BLOCKS:
            # User blocks are removed. System blocks keep their settings.
            removed = [nid for nid in self._blocks if nid >= const.USER_NID_START]
            response.payload = [self._to_payload(nid, self._blocks[nid], self._blocks[nid].name) for nid in removed]
            for nid in removed:
                del self._blocks[nid]
                self._changed_sent.pop(nid, None)
            self.update_systime()

        elif request.opcode == Opcode.CLEAR_WIFI:
            self._blocks[const.SYS_BLOCK_IDS['WiFiSettings']].message.Clear()

        elif request.opcode == Opcode.FACTORY_RESET:
            self._blocks = self._default_blocks()
            self._changed_sent.clear()
            self.update_systime()

        elif request.opcode == Opcode.FIRMWARE_UPDATE:
            pass

        else:
            response.error = ErrorCode.INVALID_OPCODE

        return response

    async def send_request(self, request_b64: str):
        self.update_systime()
        request = self._codec.decode_request(request_b64)
        response = await self.handle_command(request)

        if response:
            await self.on_response(self._codec.encode_response(response))

    async def connect(self):
        self.connected.set()

    async def close(self):
        self.disconnected.set()


async def connect_mock(callbacks: ConnectionCallbacks) -> ConnectionImplBase:
    config = utils.get_config()
    conn = MockConnection(config.device_id, callbacks)
    await conn.connect()
    return conn
