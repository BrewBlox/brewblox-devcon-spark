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
from typing import Union

from aiohttp import web
from brewblox_service import features, strex

from brewblox_devcon_spark import codec, connection, const, service_status
from brewblox_devcon_spark.__main__ import LOGGER
from brewblox_devcon_spark.models import (EncodedPayload, EncodedRequest,
                                          EncodedResponse, ErrorCode,
                                          FirmwareBlock, Opcode, ResetData,
                                          ResetReason)


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

    async def run(self):
        try:
            await service_status.wait_autoconnecting(self.app)
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

    async def write(self, request_b64: Union[str, bytes]):  # pragma: no cover
        try:
            self.update_ticks()
            _, dict_content = await self._codec.decode(
                (codec.REQUEST_TYPE, None),
                request_b64,
            )
            request = EncodedRequest(**dict_content)
            payload = request.payload
            if payload:
                (in_blockType, _), in_content = await self._codec.decode(
                    (payload.blockType, payload.subtype),
                    payload.content,
                )
            else:
                in_blockType = 0
                in_content = None

            response = EncodedResponse(
                msgId=request.msgId,
                error=ErrorCode.OK,
                payload=[]
            )

            if self.next_error:
                error = self.next_error.pop(0)
                if error is None:
                    return  # No response at all
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
                block = self._blocks.get(payload.blockId)
                if not block:
                    response.error = ErrorCode.INVALID_BLOCK_ID
                else:
                    (blockType, subtype), content = await self._codec.encode(
                        (block.type, None),
                        block.data,
                    )

                    response.payload = [EncodedPayload(
                        blockId=block.nid,
                        blockType=blockType,
                        subtype=subtype,
                        content=content
                    )]

            elif request.opcode in [
                Opcode.BLOCK_READ_ALL,
                Opcode.STORAGE_READ_ALL,
            ]:
                for block in self._blocks.values():
                    (blockType, subtype), content = await self._codec.encode(
                        (block.type, None),
                        block.data,
                    )
                    response.payload.append(EncodedPayload(
                        blockId=block.nid,
                        blockType=blockType,
                        subtype=subtype,
                        content=content,
                    ))

            elif request.opcode == Opcode.BLOCK_WRITE:
                block = self._blocks.get(payload.blockId)
                if not block:
                    response.error = ErrorCode.INVALID_BLOCK_ID
                elif not in_content:
                    response.error = ErrorCode.INVALID_BLOCK
                elif in_blockType != block.type:
                    response.error = ErrorCode.INVALID_BLOCK_TYPE
                else:
                    block.data = in_content
                    (blockType, subtype), data = await self._codec.encode(
                        (block.type, None),
                        block.data,
                    )
                    response.payload = [EncodedPayload(
                        blockId=block.nid,
                        blockType=blockType,
                        subtype=subtype,
                        data=data
                    )]

            elif request.opcode == Opcode.BLOCK_CREATE:
                nid = payload.blockId
                block = self._blocks.get(nid)
                if block:
                    response.error = ErrorCode.BLOCK_NOT_CREATABLE
                elif nid > 0 and nid < const.USER_NID_START:
                    response.error = ErrorCode.BLOCK_NOT_CREATABLE
                elif not in_content:
                    response.error = ErrorCode.INVALID_BLOCK
                else:
                    nid = nid or next(self._id_counter)
                    block = FirmwareBlock(
                        nid=nid,
                        type=in_blockType,
                        data=in_content,
                    )
                    self._blocks[nid] = block
                    (blockType, subtype), content = await self._codec.encode(
                        (block.type, None),
                        block.data,
                    )
                    response.payload = [EncodedPayload(
                        blockId=block.nid,
                        blockType=blockType,
                        subtype=subtype,
                        content=content,
                    )]

            elif request.opcode == Opcode.BLOCK_DELETE:
                nid = payload.blockId
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
                (blockType, subtype), content = await self._codec.encode(
                    (block.type, None),
                    block.data,
                )
                response.payload = [EncodedPayload(
                    blockId=block.nid,
                    blockType=blockType,
                    subtype=subtype,
                    content=content,
                )]

            elif request.opcode == Opcode.REBOOT:
                self._start_time = datetime.now()
                self.update_ticks()

            elif request.opcode == Opcode.CLEAR_BLOCKS:
                self._blocks = default_blocks()
                self.update_ticks()

            elif request.opcode == Opcode.CLEAR_WIFI:
                self._blocks[const.WIFI_SETTINGS_NID]['data'] = {}

            elif request.opcode == Opcode.FACTORY_RESET:
                self._blocks = default_blocks()
                self.update_ticks()

            elif request.opcode == Opcode.FIRMWARE_UPDATE:
                pass

            else:
                response.error = ErrorCode.INVALID_OPCODE

            _, response_b64 = await self._codec.encode(
                (codec.RESPONSE_TYPE, None),
                response.dict()
            )
            await self._on_data(response_b64)

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
