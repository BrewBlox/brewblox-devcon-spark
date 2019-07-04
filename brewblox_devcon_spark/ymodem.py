"""
Communicates with devices using the YMODEM protocol
"""

import asyncio
import math
import os
import re
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Awaitable, ByteString, List

import aiofiles
from brewblox_service import brewblox_logger

YMODEM_TRIGGER_BAUD_RATE = 28800
YMODEM_TRANSFER_BAUD_RATE = 9600

LOGGER = brewblox_logger(__name__)


@dataclass
class SendState:
    seq: int
    response: int


@dataclass
class Connection:
    address: Any
    transport: asyncio.Transport
    protocol: asyncio.Protocol

    @contextmanager
    def autoclose(self):
        try:
            yield
        finally:
            self.transport.close()


@dataclass
class HandshakeMessage:
    name: str
    git_version: str
    proto_version: str
    git_date: str
    proto_date: str
    sys_version: str
    platform: str


class FileSenderProtocol(asyncio.Protocol):
    def __init__(self):
        self._loop = asyncio.get_event_loop()
        self._connection_made_event = asyncio.Event()
        self._queue = asyncio.Queue()

    @property
    def message(self) -> Awaitable[ByteString]:
        return self._queue.get()

    @property
    def connected(self) -> Awaitable:
        return self._connection_made_event.wait()

    def connection_made(self, transport):
        self._connection_made_event.set()

    def connection_lost(self, exc):
        pass

    def data_received(self, data):
        LOGGER.debug(f'recv: {data}')
        self._loop.create_task(self._queue.put(data))

    def clear(self):
        for i in range(self._queue.qsize()):
            self._queue.get_nowait()


class FileSender():
    """
    Receive_Packet
    - first byte SOH/STX (for 128/1024 byte size packets)
    - EOT (end)
    - CA CA abort
    - ABORT1 or ABORT2 is abort
    Then 2 bytes for seq-no (although the sequence number isn't checked)
    Then the packet data
    Then CRC16?
    First packet sent is a filename packet:
    - zero-terminated filename
    - file size (ascii) followed by space?
    """

    SOH = 1     # 128 byte blocks
    STX = 2     # 1K blocks
    EOT = 4
    ACK = 6
    NAK = 0x15
    CA = 0x18           # 24
    CRC16 = 0x43        # 67
    ABORT1 = 0x41       # 65
    ABORT2 = 0x61       # 97

    PACKET_MARK = STX
    DATA_LEN = 1024 if PACKET_MARK == STX else 128
    PACKET_LEN = DATA_LEN + 5

    async def connect_tcp(self, host, port) -> Awaitable[Connection]:
        LOGGER.info(f'Connecting to {host}:{port}...')
        transport, protocol = await asyncio.get_event_loop().create_connection(FileSenderProtocol, host, port)
        conn = Connection(f'{host}:{port}', transport, protocol)
        await conn.protocol.connected
        return conn

    async def transfer(self, conn: Connection):
        handshake = await self._trigger(conn)
        filename = f'binaries/brewblox-{handshake.platform}.bin'

        LOGGER.info(f'Controller is in transfer mode, sending file {filename}')
        async with aiofiles.open(filename, 'rb') as file:
            await file.seek(0, os.SEEK_END)
            fsize = await file.tell()
            num_packets = math.ceil(fsize / FileSender.DATA_LEN)
            await file.seek(0, os.SEEK_SET)

            LOGGER.info('Sending header...')
            state: SendState = await self._send_header(conn, 'binary', fsize)

            if state.response != FileSender.ACK:
                raise ConnectionAbortedError(f'Failed with code {state.response} while sending header')

            LOGGER.info('Sending firmware...')
            for i in range(num_packets):
                current = i + 1  # packet 0 was the header
                LOGGER.debug(f'Sending packet {current} / {num_packets}')
                data = await file.read(FileSender.DATA_LEN)
                state = await self._send_data(conn, current, list(data))

                if state.response != FileSender.ACK:
                    raise ConnectionAbortedError(
                        f'Failed with code {state.response} while sending package {current}')

            await self._send_close(conn)

    async def _trigger(self, conn: Connection) -> Awaitable[HandshakeMessage]:
        message = None

        # Trigger handshake
        buffer = ''
        conn.transport.write(b'\n')
        for i in range(10):
            buffer += (await conn.protocol.message).decode()
            if '\n' in buffer:
                args = re.search(r'<!(?P<message>[^>]*)>', buffer).group('message').split(',')
                message = HandshakeMessage(*args)
                LOGGER.info(message)
                break
        else:
            raise TimeoutError('Controller did not send handshake message')

        # Trigger YMODEM mode
        buffer = ''
        conn.transport.write(b'F\n')
        for i in range(10):
            buffer += (await conn.protocol.message).decode()
            if '<!READY_FOR_FIRMWARE>' in buffer:
                LOGGER.info('Controller is ready for firmware')
                break
        else:
            raise TimeoutError('Controller did not enter file transfer mode')

        ack = 0
        while ack < 2:
            conn.transport.write(b' ')
            if (await conn.protocol.message)[0] == FileSender.ACK:
                ack += 1

        return message

    async def _send_close(self, conn: Connection):
        # Send End Of Transfer
        assert await self._send_packet(conn, [FileSender.EOT]) == FileSender.ACK
        assert await self._send_packet(conn, [FileSender.EOT]) == FileSender.ACK

        # Signal end of connection
        await self._send_data(conn, 0, [])

    async def _send_header(self, conn: Connection, name: str, size: int) -> Awaitable[SendState]:
        data = [FileSender.PACKET_MARK, *name.encode(), 0, *f'{size} '.encode()]
        return await self._send_data(conn, 0, data)

    async def _send_data(self, conn: Connection, seq: int, data: List[int]) -> Awaitable[SendState]:
        packet_data = data + [0] * (FileSender.DATA_LEN - len(data))
        packet_seq = seq & 0xFF
        packet_seq_neg = 0xFF - packet_seq
        crc16 = [0, 0]

        packet = [FileSender.PACKET_MARK, packet_seq, packet_seq_neg, *packet_data, *crc16]
        if len(packet) != FileSender.PACKET_LEN:
            raise RuntimeError(f'Packet length mismatch: {len(packet)} / {FileSender.PACKET_LEN}')

        response = await self._send_packet(conn, packet)

        if response == FileSender.NAK:
            LOGGER.info('Retrying packet...')
            await asyncio.sleep(1)
            response = await self._send_packet(conn, packet)

        return SendState(seq, response)

    async def _send_packet(self, conn: Connection, packet: str) -> int:
        conn.protocol.clear()
        conn.transport.write(bytes(packet))
        while True:
            retv = [int(i) for i in await conn.protocol.message][0]
            if retv != FileSender.CRC16:
                break

        return retv
