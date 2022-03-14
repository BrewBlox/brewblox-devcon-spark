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


def default_objects() -> dict[int, FirmwareBlock]:
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
                data={},
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
        self._objects: dict[int, FirmwareBlock] = default_objects()

    @property
    def connected(self) -> bool:  # pragma: no cover
        return True

    def update_ticks(self):
        elapsed = datetime.now() - self._start_time
        ticks_block = self._objects[const.SYSTIME_NID]
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

    async def write(self, msg: Union[str, bytes]):  # pragma: no cover
        try:
            self.update_ticks()
            _, dec_data = await self._codec.decode((codec.REQUEST_TYPE, None), msg)
            request = EncodedRequest(**dec_data)
            payload = request.payload
            if payload:
                req_payload_ident, req_payload_data = await self._codec.decode(
                    (payload.objtype, payload.subtype),
                    payload.data,
                )
            else:
                req_payload_ident = (0, 0)
                req_payload_data = None

            response = EncodedResponse(
                msgId=request.msgId,
                error=ErrorCode.ERR_OK,
                payload=[]
            )

            if self.next_error:
                error = self.next_error.pop(0)
                if error is None:
                    return  # No response at all
                else:
                    response.error = error

            elif request.opcode == Opcode.OPCODE_NONE:
                await self.welcome()

            elif request.opcode in [
                Opcode.OPCODE_READ_OBJECT,
                Opcode.OPCODE_READ_STORED_OBJECT
            ]:
                block = self._objects.get(payload.blockId)
                if not block:
                    response.error = ErrorCode.ERR_INVALID_OBJECT_ID
                else:
                    (objtype, subtype), data = await self._codec.encode(
                        (block.type, None),
                        block.data,
                    )

                    response.payload = [EncodedPayload(
                        blockId=block.nid,
                        objtype=objtype,
                        subtype=subtype,
                        data=data
                    )]

            elif request.opcode == Opcode.OPCODE_WRITE_OBJECT:
                block = self._objects.get(payload.blockId)
                if not block:
                    response.error = ErrorCode.ERR_INVALID_OBJECT_ID
                elif not req_payload_data:
                    response.error = ErrorCode.ERR_OBJECT_DATA_NOT_ACCEPTED
                elif req_payload_ident[0] != block.type:
                    response.error = ErrorCode.ERR_INVALID_OBJECT_TYPE
                else:
                    block.data = req_payload_data
                    (objtype, subtype), data = await self._codec.encode(
                        (block.type, None),
                        block.data,
                    )
                    response.payload = [EncodedPayload(
                        blockId=block.nid,
                        objtype=objtype,
                        subtype=subtype,
                        data=data
                    )]

            elif request.opcode == Opcode.OPCODE_CREATE_OBJECT:
                nid = payload.blockId
                block = self._objects.get(nid)
                if block:
                    response.error = ErrorCode.ERR_OBJECT_NOT_CREATABLE
                elif nid > 0 and nid < const.USER_NID_START:
                    response.error = ErrorCode.ERR_OBJECT_NOT_CREATABLE
                elif not req_payload_data:
                    response.error = ErrorCode.ERR_OBJECT_DATA_NOT_ACCEPTED
                else:
                    nid = nid or next(self._id_counter)
                    block = FirmwareBlock(
                        nid=nid,
                        type=req_payload_ident[0],
                        data=req_payload_data,
                    )
                    self._objects[nid] = block
                    (objtype, subtype), data = await self._codec.encode(
                        (block.type, None),
                        block.data,
                    )
                    response.payload = [EncodedPayload(
                        blockId=block.nid,
                        objtype=objtype,
                        subtype=subtype,
                        data=data
                    )]

            elif request.opcode == Opcode.OPCODE_DELETE_OBJECT:
                nid = payload.blockId
                block = self._objects.get(nid)
                if not block:
                    response.error = ErrorCode.ERR_OBJECT_NOT_DELETABLE
                elif nid < const.USER_NID_START:
                    response.error = ErrorCode.ERR_OBJECT_NOT_DELETABLE
                else:
                    del self._objects[nid]

            elif request.opcode in [
                Opcode.OPCODE_LIST_OBJECTS,
                Opcode.OPCODE_LIST_STORED_OBJECTS
            ]:
                for block in self._objects.values():
                    (objtype, subtype), data = await self._codec.encode(
                        (block.type, None),
                        block.data,
                    )
                    response.payload.append(EncodedPayload(
                        blockId=block.nid,
                        objtype=objtype,
                        subtype=subtype,
                        data=data
                    ))

            elif request.opcode == Opcode.OPCODE_CLEAR_OBJECTS:
                self._objects = default_objects()
                self.update_ticks()

            elif request.opcode == Opcode.OPCODE_REBOOT:
                self._start_time = datetime.now()
                self.update_ticks()

                # No response
                return

            elif request.opcode == Opcode.OPCODE_FACTORY_RESET:
                # No response
                return

            elif request.opcode == Opcode.OPCODE_LIST_COMPATIBLE_OBJECTS:
                pass

            elif request.opcode == Opcode.OPCODE_DISCOVER_OBJECTS:
                # Always return spark pins when discovering blocks
                block = self._objects[const.SPARK_PINS_NID]
                (objtype, subtype), data = await self._codec.encode(
                    (block.type, None),
                    block.data,
                )
                response.payload = [EncodedPayload(
                    blockId=block.nid,
                    objtype=objtype,
                    subtype=subtype,
                    data=data
                )]

            elif request.opcode == Opcode.OPCODE_FIRMWARE_UPDATE:
                pass

            else:
                response.error = ErrorCode.ERR_INVALID_COMMAND

            _, resp_str = await self._codec.encode(
                (codec.RESPONSE_TYPE, None),
                response.dict()
            )
            await self._on_data(resp_str)

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
