"""
Transfer firmware files to Particle-based Spark controllers using the YMODEM protocol.

Spec: http://pauillac.inria.fr/~doligez/zmodem/ymodem.txt
Reference: https://github.com/particle-iot/particle-cli/blob/master/src/lib/ymodem.js

The default handler on the controller side is controlbox.
After a firmware update command, controlbox will hand over the serial to the OTA handler.

OTA procedure:
- Send controlbox firmware update command (not handled here).
- Connect to TCP.
- Write newline characters until the controller responds with a handshake.
    - Handshakes are formatted as controlbox events.
    - The firmware update handshake is different from the generic controlbox handshake.
- Trigger YMODEM by writing 'F\n' until controller responds with a "ready for firmware" event.
- Ensure YMODEM is active by writing ' ' until controller responded twice with ACK.
- Transfer file using YMODEM protocol
    - >> file header      STX 0x00 0xFF {FILENAME} {FILE LENGTH} {NULL}[1024 - header length] {CRC}[2]
    - <<                  ACK
    - <<                  C
    - >> file packet      STX 0x01 0xFE {DATA}[1024] {CRC}[2]
    - <<                  ACK
    - >> file packet      STX 0x02 0xFD {DATA}[1024] {CRC}[2]
    - <<                  ACK
    - ...
    - >> file end         EOT
    - <<                  ACK
    - >> transfer end     STX 0x00 0xFF {NULL}[1024]
- Close connection. The controller will automatically restart.

Notes:
- The file name in the header is a null-terminated file name.
- The file length in the header is a space-terminated string (eg. '252464 ').
- YMODEM supports 256-byte (SOH) and 1024-byte (STX) packet length. STX / 1024 is used here.
- The header packet is padded with NULL bytes to reach packet length.
- For the last file packet, the data is padded with NULL bytes to reach packet length.
- Control characters (STX, index, negating index, CRC) do not count towards the packet length.
- The second and third byte in packages are its index and 0xFF - index. The header always has index 0x00.
- CRC bytes are transmitted, but ignored. The reference implementation always sends [0,0] CRC.
"""

import asyncio
import logging
import math
import os
import re
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from enum import IntEnum
from pathlib import Path
from typing import Awaitable, ByteString

import aiofiles

TCP_CONNECT_INTERVAL = timedelta(seconds=3)
NAK_RETRY_DELAY = timedelta(milliseconds=100)
CONNECT_ATTEMPTS = 5

LOGGER = logging.getLogger(__name__)


class Control(IntEnum):
    SOH = 0x01          # 01 - 128 byte blocks
    STX = 0x02          # 02 - 1K blocks
    EOT = 0x04          # 04 - End Of Transfer
    EOF = 0x1A          # 26 - End Of File
    ACK = 0x06          # 06 - Acknowledge
    NAK = 0x15          # 21 - Negative Acknowledge
    CAN = 0x18          # 24 - Cancel
    C = 0x43            # 67 - Continue


@dataclass
class Connection:
    address: str
    process: subprocess.Popen | None
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


async def connect_tcp(address: str, proc: subprocess.Popen = None) -> Connection:
    LOGGER.info(f'Connecting to {address}...')
    host, port = address.split(':')
    loop = asyncio.get_event_loop()
    transport, protocol = await loop.create_connection(FileSenderProtocol, host, port)
    conn = Connection(f'{host}:{port}', proc, transport, protocol)
    await conn.protocol.connected
    return conn


async def connect(address: str) -> Connection:
    for _ in range(CONNECT_ATTEMPTS):
        try:
            await asyncio.sleep(TCP_CONNECT_INTERVAL.total_seconds())
            return await connect_tcp(address)
        except ConnectionRefusedError:
            LOGGER.debug('Connection refused, retrying...')
    raise ConnectionRefusedError()


class OtaClient():
    PACKET_MARK = Control.STX
    DATA_LEN = 1024 if PACKET_MARK == Control.STX else 128
    PACKET_LEN = DATA_LEN + 5

    def __init__(self, notify_cb):
        self._notify = notify_cb

    async def send(self, conn: Connection, filename: str):
        await self._trigger_ymodem(conn)
        await self._transfer(conn, filename)

    async def _trigger_ymodem(self, conn: Connection) -> HandshakeMessage:
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
                message = HandshakeMessage(*args[:7])
                self._notify(f'Handshake received: {message}')
                break
        else:
            raise asyncio.TimeoutError('Controller did not send handshake message')

        # Trigger YMODEM mode
        buffer = ''
        conn.transport.write(b'F\n')
        for i in range(10):
            buffer += (await conn.protocol.message).decode()
            if '<!READY_FOR_FIRMWARE>' in buffer:
                self._notify('Controller is ready for firmware')
                break
        else:
            raise asyncio.TimeoutError('Controller did not enter file transfer mode')

        ack = 0
        while ack < 2:
            conn.transport.write(b' ')
            if (await conn.protocol.message)[0] == Control.ACK:
                ack += 1

        return message

    async def _transfer(self, conn: Connection, filename: str):
        path = Path(filename)
        self._notify(f'Starting file transfer for {path.name}')
        async with aiofiles.open(path, 'rb') as file:
            await file.seek(0, os.SEEK_END)
            fsize = await file.tell()
            num_packets = math.ceil(fsize / OtaClient.DATA_LEN)
            await file.seek(0, os.SEEK_SET)

            self._notify('Sending file header')
            response = await self._send_header(conn, path.name, fsize)

            if response != Control.ACK:
                raise ConnectionAbortedError(f'Failed with code {response.name} while sending header')

            self._notify('Sending file body')
            for i in range(num_packets):
                current = i + 1  # packet 0 was the header
                LOGGER.debug(f'Sending packet {current} / {num_packets}')
                data = await file.read(OtaClient.DATA_LEN)
                response = await self._send_data(conn, current, list(data))

                if response != Control.ACK:
                    raise ConnectionAbortedError(
                        f'Failed with code {response.name} while sending package {current}')

        LOGGER.debug('Sending EOT')
        assert await self._send_packet(conn, [Control.EOT]) == Control.ACK

        LOGGER.debug('Sending closing header')
        await self._send_data(conn, 0, [])

        self._notify('File transfer done!')

    async def _send_header(self, conn: Connection, name: str, size: int) -> Control:
        data = [OtaClient.PACKET_MARK, *name.encode(), 0, *f'{size} '.encode()]
        return await self._send_data(conn, 0, data)

    async def _send_data(self, conn: Connection, seq: int, data: list[int]) -> Control:
        packet_data = data + [0] * (OtaClient.DATA_LEN - len(data))
        packet_seq = seq & 0xFF
        packet_seq_neg = 0xFF - packet_seq
        crc16 = [0, 0]

        packet = [OtaClient.PACKET_MARK, packet_seq, packet_seq_neg, *packet_data, *crc16]
        if len(packet) != OtaClient.PACKET_LEN:
            raise RuntimeError(f'Packet length mismatch: {len(packet)} / {OtaClient.PACKET_LEN}')

        response = await self._send_packet(conn, packet)

        if response == Control.NAK:
            LOGGER.debug('Retrying packet...')
            await asyncio.sleep(NAK_RETRY_DELAY.total_seconds())
            response = await self._send_packet(conn, packet)

        return response

    async def _send_packet(self, conn: Connection, packet: str) -> Control:
        conn.protocol.clear()
        conn.transport.write(bytes(packet))
        while True:
            resp: Control = Control((await conn.protocol.message)[0])

            # C is a continue prompt from receiver, and can be ignored
            if resp == Control.C:
                continue

            return resp
