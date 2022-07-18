"""
An in-process firmware simulation.
This is not intended to simulate firmware processes,
only to provide encoded responses that make some sense.

connection_sim.py serves as a short-circuit replacement of connection.py
Instead of binary data being written to a stream,
it is decoded and immediately replied to.
This prevents having to spin up a simulator in a separate process for tests.
"""

import asyncio
from datetime import datetime
from itertools import count
from typing import Optional, Union

from aiohttp import web
from brewblox_service import features, strex

from brewblox_devcon_spark import codec, connection, const, service_status
from brewblox_devcon_spark.__main__ import LOGGER
from brewblox_devcon_spark.codec import bloxfield
from brewblox_devcon_spark.models import (DecodedPayload, EncodedPayload,
                                          ErrorCode, FirmwareBlock,
                                          IntermediateRequest,
                                          IntermediateResponse, Opcode,
                                          ResetData, ResetReason)


def default_blocks() -> dict[int, FirmwareBlock]:
    return {
        block.nid: block
        for block in [
            FirmwareBlock(
                nid=const.SYSINFO_NID,
                type='SysInfo',
                data={
                    'deviceId': 'FACADE'
                },
            ),
            FirmwareBlock(
                nid=const.SYSTIME_NID,
                type='Ticks',
                data={
                    'millisSinceBoot': 0,
                    'secondsSinceEpoch': 0,
                },
            ),
            FirmwareBlock(
                nid=const.ONEWIREBUS_NID,
                type='OneWireBus',
                data={},
            ),
            FirmwareBlock(
                nid=const.WIFI_SETTINGS_NID,
                type='WiFiSettings',
                data={},
            ),
            FirmwareBlock(
                nid=const.TOUCH_SETTINGS_NID,
                type='TouchSettings',
                data={},
            ),
            FirmwareBlock(
                nid=const.DISPLAY_SETTINGS_NID,
                type='DisplaySettings',
                data={
                    'timeZone': 'Africa/Casablanca'
                },
            ),
            FirmwareBlock(
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


class SparkConnectionSim(connection.SparkConnection):

    def __init__(self, app: web.Application):
        super().__init__(app)

        self._address = 'simulation:1234'
        self._data_callbacks = set()
        self._event_callbacks = set()

        # an ErrorCode will be returned
        # a None value will cause no response to be returned
        self.next_error: list[Union[ErrorCode, None]] = []

        self._start_time = datetime.now()
        self._codec: codec.Codec = features.get(app, key='sim_codec')
        self._id_counter = count(start=const.USER_NID_START)
        self._blocks: dict[int, FirmwareBlock] = default_blocks()

    @property
    def connected(self) -> bool:  # pragma: no cover
        return True

    def _to_payload(self, block: FirmwareBlock) -> EncodedPayload:
        (blockType, subtype) = codec.split_type(block.type)
        return self._codec.encode_payload(DecodedPayload(
            blockId=block.nid,
            blockType=blockType,
            subypte=subtype,
            content=block.data
        ))

    def _to_block(self, payload: EncodedPayload) -> FirmwareBlock:
        payload = self._codec.decode_payload(payload)
        return FirmwareBlock(
            nid=payload.blockId,
            type=codec.join_type(payload.blockType, payload.subtype),
            data=payload.content,
        )

    def _default_block(self, block_id: int, block_type: str) -> FirmwareBlock:
        return self._to_block(
            self._codec.encode_payload(
                DecodedPayload(
                    blockId=block_id,
                    blockType=block_type,
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

    def update_ticks(self):
        elapsed = datetime.now() - self._start_time
        ticks_block = self._blocks[const.SYSTIME_NID]
        ticks_block.data['millisSinceBoot'] = elapsed.total_seconds() * 1000
        ticks_block.data['secondsSinceEpoch'] = self._start_time.timestamp() + elapsed.total_seconds()

    async def welcome(self):
        welcome = [
            'BREWBLOX',
            self.app['ini']['firmware_version'],
            self.app['ini']['proto_version'],
            self.app['ini']['firmware_date'],
            self.app['ini']['proto_date'],
            self.app['ini']['system_version'],
            self._address,
            ResetReason.NONE.value,
            ResetData.NOT_SPECIFIED.value,
            self.app['config']['device_id'] or '1234567F0CASE',
        ]
        await self._on_event(','.join(welcome))

    async def handle_command(self, request: IntermediateRequest) -> Optional[IntermediateResponse]:  # pragma: no cover
        response = IntermediateResponse(
            msgId=request.msgId,
            error=ErrorCode.OK,
            payload=[]
        )

        if self.next_error:
            error = self.next_error.pop(0)
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
            Opcode.STORAGE_READ
        ]:
            block = self._blocks.get(request.payload.blockId)
            if not block:
                response.error = ErrorCode.INVALID_BLOCK_ID
            else:
                response.payload = [self._to_payload(block)]

        elif request.opcode in [
            Opcode.BLOCK_READ_ALL,
            Opcode.STORAGE_READ_ALL,
        ]:
            response.payload = [self._to_payload(block)
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
                response.payload = [self._to_payload(block)]

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
                block = self._default_block(nid, argblock.type)
                self._merge_blocks(block, argblock)
                self._blocks[nid] = block
                response.payload = [self._to_payload(block)]

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
            response.payload = [self._to_payload(block)]

        elif request.opcode == Opcode.REBOOT:
            self._start_time = datetime.now()
            self.update_ticks()

        elif request.opcode == Opcode.CLEAR_BLOCKS:
            response.payload = [self._to_payload(block)
                                for block in self._blocks.values()
                                if block.nid >= const.USER_NID_START]
            self._blocks = default_blocks()
            self.update_ticks()

        elif request.opcode == Opcode.CLEAR_WIFI:
            self._blocks[const.WIFI_SETTINGS_NID].data.clear()

        elif request.opcode == Opcode.FACTORY_RESET:
            self._blocks = default_blocks()
            self.update_ticks()

        elif request.opcode == Opcode.FIRMWARE_UPDATE:
            pass

        else:
            response.error = ErrorCode.INVALID_OPCODE

        return response

    async def run(self):
        try:
            await service_status.wait_enabled(self.app)
            service_status.set_connected(self.app, self._address)
            self.update_ticks()
            await self.welcome()

            while True:
                await asyncio.sleep(3600)

        except Exception as ex:  # pragma: no cover
            LOGGER.error(strex(ex))
            raise ex

        finally:
            service_status.set_disconnected(self.app)

    async def start_reconnect(self):
        pass

    async def write(self, request_b64: str):  # pragma: no cover
        try:
            self.update_ticks()
            request = self._codec.decode_request(request_b64)
            response = await self.handle_command(request)

            if response:
                await self._on_data(self._codec.encode_response(response))

        except Exception as ex:
            LOGGER.error(strex(ex))
            raise ex


def setup(app: web.Application):
    # Before returning, the simulator encodes + decodes values
    # We want to avoid stripping readonly values here
    features.add(app, codec.Codec(app, strip_readonly=False), key='sim_codec')
    # Register as a SparkConnection, so connection.fget(app) still works
    features.add(app, SparkConnectionSim(app), key=connection.SparkConnection)


def fget(app: web.Application) -> SparkConnectionSim:
    return features.get(app, connection.SparkConnection)
