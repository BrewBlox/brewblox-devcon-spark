"""
An in-process firmware simulation.
This is not intended to simulate firmware processes,
only to provide encoded responses that make some sense.

MockConnection is an alternative to StreamConnection or MqttConnection.
This prevents having to spin up a simulator in a separate process for tests.
"""

import logging
from datetime import datetime
from itertools import count

from .. import codec, const, utils
from ..codec import bloxfield
from ..models import (DecodedPayload, EncodedPayload, ErrorCode, FirmwareBlock,
                      IntermediateRequest, IntermediateResponse, Opcode,
                      ReadMode, ResetData, ResetReason)
from .connection_impl import ConnectionCallbacks, ConnectionImplBase

LOGGER = logging.getLogger(__name__)

# an ErrorCode will be returned
# a None value will cause no response to be returned
NEXT_ERROR: list[ErrorCode | None] = []


def default_blocks() -> dict[int, FirmwareBlock]:
    return {
        block.nid: block
        for block in [
            FirmwareBlock(
                id='SystemInfo',
                nid=const.SYSINFO_NID,
                type='SysInfo',
                data={
                    'deviceId': 'FACADE',
                    'timeZone': 'Africa/Casablanca',
                    'updatesPerSecond': 9001,
                },
            ),
            FirmwareBlock(
                id='OneWireBus',
                nid=const.ONEWIREBUS_NID,
                type='OneWireBus',
                data={},
            ),
            FirmwareBlock(
                id='WiFiSettings',
                nid=const.WIFI_SETTINGS_NID,
                type='WiFiSettings',
                data={},
            ),
            FirmwareBlock(
                id='DisplaySettings',
                nid=const.DISPLAY_SETTINGS_NID,
                type='DisplaySettings',
                data={},
            ),
            FirmwareBlock(
                id='SparkPins',
                nid=const.SPARK_PINS_NID,
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
        ]}


class MockConnection(ConnectionImplBase):
    def __init__(self,
                 device_id: str,
                 callbacks: ConnectionCallbacks,
                 ) -> None:
        super().__init__('MOCK', device_id, callbacks)

        self._start_time = datetime.now()
        self._codec = codec.Codec(filter_values=False)
        self._id_counter = count(start=const.USER_NID_START)
        self._blocks: dict[int, FirmwareBlock] = default_blocks()

    def _to_payload(self, block: FirmwareBlock, mode: ReadMode) -> EncodedPayload:
        return self._codec.encode_payload(DecodedPayload(
            blockId=block.nid,
            blockType=block.type,
            name=block.id,
            content=block.data
        ))

    def _to_block(self, payload: EncodedPayload) -> FirmwareBlock:
        payload = self._codec.decode_payload(payload)
        return FirmwareBlock(
            id=payload.name,
            nid=payload.blockId,
            type=payload.blockType,
            data=payload.content,
        )

    def _default_block(self, block_id: str, block_nid: int, block_type: str) -> FirmwareBlock:
        return self._to_block(
            self._codec.encode_payload(
                DecodedPayload(
                    blockId=block_nid,
                    blockType=block_type,
                    name=block_id,
                    content={}
                )
            )
        )

    def _merge_blocks(self, dest: FirmwareBlock, src: FirmwareBlock):
        for key in dest.data.keys():
            v_new = src.data[key]
            if any([
                bloxfield.is_defined_link(v_new),
                bloxfield.is_defined_quantity(v_new),
                not bloxfield.is_bloxfield(v_new) and v_new is not None,
            ]):
                dest.data[key] = v_new

    def update_systime(self):
        elapsed = datetime.now() - self._start_time
        sysinfo_block = self._blocks[const.SYSINFO_NID]
        sysinfo_block.data['uptime'] = elapsed.total_seconds() * 1000
        sysinfo_block.data['systemTime'] = self._start_time.timestamp() + elapsed.total_seconds()

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
            ResetReason.NONE.value,
            ResetData.NOT_SPECIFIED.value,
            config.device_id,
        ]
        await self.on_event(','.join(welcome))

    async def handle_command(self,
                             request: IntermediateRequest
                             ) -> IntermediateResponse | None:  # pragma: no cover
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
            else:
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
            block = self._blocks.get(request.payload.blockId)
            if not block:
                response.error = ErrorCode.INVALID_BLOCK_ID
            else:
                response.payload = [self._to_payload(block, request.mode)]

        elif request.opcode in [
            Opcode.BLOCK_READ_ALL,
            Opcode.STORAGE_READ_ALL,
            Opcode.NAME_READ_ALL,
        ]:
            response.payload = [self._to_payload(block, request.mode)
                                for block in self._blocks.values()]

        elif request.opcode == Opcode.BLOCK_WRITE:
            block = self._blocks.get(request.payload.blockId)
            if not block:
                response.error = ErrorCode.INVALID_BLOCK_ID
            elif request.payload.content is None:
                response.error = ErrorCode.INVALID_BLOCK
            elif request.payload.blockType != block.type:
                response.error = ErrorCode.INVALID_BLOCK_TYPE
            else:
                src = self._to_block(request.payload)
                self._merge_blocks(block, src)
                response.payload = [self._to_payload(block, request.mode)]

        elif request.opcode == Opcode.BLOCK_CREATE:
            nid = request.payload.blockId
            block = self._blocks.get(nid)
            if block:
                response.error = ErrorCode.BLOCK_NOT_CREATABLE
            elif nid > 0 and nid < const.USER_NID_START:
                response.error = ErrorCode.BLOCK_NOT_CREATABLE
            elif request.payload.content is None:
                response.error = ErrorCode.INVALID_BLOCK
            else:
                nid = nid or next(self._id_counter)
                argblock = self._to_block(request.payload)
                block = self._default_block(request.payload.name, nid, argblock.type)
                self._merge_blocks(block, argblock)
                self._blocks[nid] = block
                response.payload = [self._to_payload(block, request.mode)]

        elif request.opcode == Opcode.BLOCK_DELETE:
            nid = request.payload.blockId
            block = self._blocks.get(nid)
            if not block:
                response.error = ErrorCode.INVALID_BLOCK_ID
            elif nid < const.USER_NID_START:
                response.error = ErrorCode.BLOCK_NOT_DELETABLE
            else:
                del self._blocks[nid]

        elif request.opcode == Opcode.BLOCK_DISCOVER:
            # Always return spark pins when discovering blocks
            block = self._blocks[const.SPARK_PINS_NID]
            response.payload = [self._to_payload(block, request.mode)]

        elif request.opcode == Opcode.NAME_WRITE:
            nid = request.payload.blockId
            name = request.payload.name
            block = self._blocks.get(nid)
            match = next((block for block in self._blocks.values()
                          if block.id == name), None)
            if not block:
                response.error = ErrorCode.INVALID_BLOCK_ID
            elif not name:
                response.error = ErrorCode.INVALID_BLOCK_NAME
            elif match and match.nid != nid:
                response.error = ErrorCode.INVALID_BLOCK_NAME
            else:
                block.id = name
                response.payload = [self._to_payload(block, ReadMode.DEFAULT)]

        elif request.opcode == Opcode.REBOOT:
            self._start_time = datetime.now()
            self.update_systime()

        elif request.opcode == Opcode.CLEAR_BLOCKS:
            response.payload = [self._to_payload(block, request.mode)
                                for block in self._blocks.values()
                                if block.nid >= const.USER_NID_START]
            self._blocks = default_blocks()
            self.update_systime()

        elif request.opcode == Opcode.CLEAR_WIFI:
            self._blocks[const.WIFI_SETTINGS_NID].data.clear()

        elif request.opcode == Opcode.FACTORY_RESET:
            self._blocks = default_blocks()
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
