"""
Communicates with devices using the YMODEM protocol
"""

import asyncio
import math
import os
import re
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Any, Awaitable, ByteString, Optional

import aiofiles
from brewblox_service import brewblox_logger, strex

YMODEM_TRIGGER_BAUD_RATE = 28800
YMODEM_TRANSFER_BAUD_RATE = 115200

LOGGER = brewblox_logger(__name__)


@dataclass
class SendState:
    seq: int
    response: int


@dataclass
class Connection:
    address: Any
    process: Optional[subprocess.Popen]
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
        self._connection_made_event = asyncio.Event()
        self._queue = asyncio.Queue()

    @property
    def message(self) -> Awaitable[ByteString]:
        return self._queue.get()

    @property
    def connected(self) -> Awaitable[None]:
        return self._connection_made_event.wait()

    def connection_made(self, transport):
        self._connection_made_event.set()

    def connection_lost(self, exc):
        LOGGER.info('Firmware update connection closed')

    def data_received(self, data):
        LOGGER.debug(f'recv: {data}')
        self._queue.put_nowait(data)

    def clear(self):
        for i in range(self._queue.qsize()):
            self._queue.get_nowait()


def is_tcp(address) -> str:
    return ':' in address


async def connect_tcp(address, proc: subprocess.Popen = None) -> Connection:
    LOGGER.info(f'Connecting to {address}...')
    host, port = address.split(':')
    loop = asyncio.get_event_loop()
    transport, protocol = await loop.create_connection(FileSenderProtocol, host, port)
    conn = Connection(f'{host}:{port}', proc, transport, protocol)
    await conn.protocol.connected
    return conn


async def connect_serial(address) -> Connection:
    LOGGER.info(f'Creating bridge for {address}')

    proc = subprocess.Popen([
        '/usr/bin/socat',
        'tcp-listen:8332,reuseaddr,fork',
        f'file:{address},raw,echo=0,b{YMODEM_TRANSFER_BAUD_RATE}'
    ])

    last_err = None
    for _ in range(5):
        try:
            await asyncio.sleep(1)
            return await connect_tcp('localhost:8332', proc)
        except OSError as ex:
            last_err = strex(ex)
            LOGGER.debug(f'Subprocess connection error: {last_err}')

    raise ConnectionError(last_err)


async def connect(address) -> Connection:
    if is_tcp(address):
        return await connect_tcp(address)
    else:
        return await connect_serial(address)


class Control(IntEnum):
    SOH = 0x01          # 01 - 128 byte blocks
    STX = 0x02          # 02 - 1K blocks
    EOT = 0x04          # 04 - End Of Transfer
    EOF = 0x1A          # 26 - End Of File
    ACK = 0x06          # 06 - Acknowledge
    NAK = 0x15          # 21 - Negative Acknowledge
    CAN = 0x18          # 24 - Cancel
    C = 0x43            # 67 - Continue


class FileSender():
    """
    See: http://pauillac.inria.fr/~doligez/zmodem/ymodem.txt
    """

    PACKET_MARK = Control.STX
    DATA_LEN = 1024 if PACKET_MARK == Control.STX else 128
    PACKET_LEN = DATA_LEN + 5

    def __init__(self, notify_cb):
        self._notify = notify_cb

    async def start_session(self, conn: Connection) -> HandshakeMessage:
        message = None

        async def _read():
            return (await conn.protocol.message).decode()

        # Trigger handshake
        buffer = ''
        conn.transport.write(b'\n')
        for i in range(20):
            try:
                buffer += await asyncio.wait_for(_read(), 1)
            except asyncio.TimeoutError:
                LOGGER.debug('Repeating handshake trigger...')
                conn.transport.write(b'\n')
                continue

            if re.search(r'<!(?P<message>BREWBLOX[^>]*)>', buffer):
                raise ConnectionResetError('Connected to wrong protocol (controlbox handshake received)')

            match = re.search(r'<!(?P<message>FIRMWARE_UPDATER[^>]*)>', buffer)
            if match:
                args = match.group('message').split(',')
                message = HandshakeMessage(*args)
                self._notify(f'Handshake received: {message}')
                break
        else:
            raise TimeoutError('Controller did not send handshake message')

        # Trigger YMODEM mode
        buffer = ''
        conn.transport.write(b'F\n')
        for i in range(10):
            buffer += (await conn.protocol.message).decode()
            if '<!READY_FOR_FIRMWARE>' in buffer:
                self._notify('Controller is ready for firmware')
                break
        else:
            raise TimeoutError('Controller did not enter file transfer mode')

        ack = 0
        while ack < 2:
            conn.transport.write(b' ')
            if (await conn.protocol.message)[0] == Control.ACK:
                ack += 1

        return message

    async def transfer(self, conn: Connection, filename: str):
        path = Path(filename)
        self._notify(f'Controller is in transfer mode, sending file {path.name}')
        async with aiofiles.open(path, 'rb') as file:
            await file.seek(0, os.SEEK_END)
            fsize = await file.tell()
            num_packets = math.ceil(fsize / FileSender.DATA_LEN)
            await file.seek(0, os.SEEK_SET)

            self._notify('Sending file header')
            state: SendState = await self._send_header(conn, path.name, fsize)

            if state.response != Control.ACK:
                raise ConnectionAbortedError(f'Failed with code {Control(state.response).name} while sending header')

            self._notify('Sending file data')
            for i in range(num_packets):
                current = i + 1  # packet 0 was the header
                LOGGER.debug(f'Sending packet {current} / {num_packets}')
                data = await file.read(FileSender.DATA_LEN)
                state = await self._send_data(conn, current, list(data))

                if state.response != Control.ACK:
                    raise ConnectionAbortedError(
                        f'Failed with code {Control(state.response).name} while sending package {current}')

        # Send End Of Transfer
        LOGGER.debug('Sending EOT 1')
        assert await self._send_packet(conn, [Control.EOT]) == Control.ACK
        LOGGER.debug('Sending EOT 2')
        assert await self._send_packet(conn, [Control.EOT]) == Control.ACK

    async def end_session(self, conn):
        await self._send_data(conn, 0, [])

    async def _send_header(self, conn: Connection, name: str, size: int) -> SendState:
        data = [FileSender.PACKET_MARK, *name.encode(), 0, *f'{size} '.encode()]
        return await self._send_data(conn, 0, data)

    async def _send_data(self, conn: Connection, seq: int, data: list[int]) -> SendState:
        packet_data = data + [0] * (FileSender.DATA_LEN - len(data))
        packet_seq = seq & 0xFF
        packet_seq_neg = 0xFF - packet_seq
        crc16 = [0, 0]

        packet = [FileSender.PACKET_MARK, packet_seq, packet_seq_neg, *packet_data, *crc16]
        if len(packet) != FileSender.PACKET_LEN:
            raise RuntimeError(f'Packet length mismatch: {len(packet)} / {FileSender.PACKET_LEN}')

        response = await self._send_packet(conn, packet)

        if response == Control.NAK:
            LOGGER.debug('Retrying packet...')
            await asyncio.sleep(1)
            response = await self._send_packet(conn, packet)

        return SendState(seq, response)

    async def _read_character(self, conn: Connection) -> int:
        resp = await conn.protocol.message
        return resp[0]

    async def _send_packet(self, conn: Connection, packet: str) -> int:
        conn.protocol.clear()
        conn.transport.write(bytes(packet))
        while True:
            resp = await self._read_character(conn)
            if resp == Control.C:
                continue
            return resp
