"""
Stream-based connections to the Spark.
The connection itself is always TCP.
For serial and simulation targets, the TCP server is a subprocess.
"""

import asyncio
import platform
from contextlib import suppress
from pathlib import Path
from subprocess import Popen
from typing import Optional, Union

from aiohttp import web
from brewblox_service import brewblox_logger, strex
from serial.tools import list_ports

from brewblox_devcon_spark import exceptions, mdns

from .base_connection import BaseConnection
from .cbox_parser import ControlboxParser

LOGGER = brewblox_logger(__name__)

DISCOVERY_DNS_TIMEOUT_S = 20
BREWBLOX_DNS_TYPE = '_brewblox._tcp.local.'
SUBPROCESS_HOST = 'localhost'
SUBPROCESS_PORT = 8332
SUBPROCESS_CONNECT_INTERVAL_S = 1
SUBPROCESS_CONNECT_RETRY_COUNT = 10
USB_BAUD_RATE = 115200

SIM_BINARIES = {
    'x86_64': 'brewblox-amd64.sim',
    'armv7l': 'brewblox-arm32.sim',
    'aarch64': 'brewblox-arm64.sim'
}

SPARK_HWIDS = [
    r'USB VID\:PID=2B04\:C006.*',  # Photon
    r'USB VID\:PID=2B04\:C008.*',  # P1
]

# Construct a regex OR'ing all allowed hardware ID matches
# Example result: (?:HWID_REGEX_ONE|HWID_REGEX_TWO)
SPARK_DEVICE_REGEX = f'(?:{"|".join([dev for dev in SPARK_HWIDS])})'


class StreamConnection(BaseConnection):

    def __init__(self,
                 address: str,
                 reader: asyncio.StreamReader,
                 writer: asyncio.StreamWriter,
                 ) -> None:
        super().__init__(address)

        self._reader = reader
        self._writer = writer
        self._parser = ControlboxParser()

    @property
    def connected(self) -> bool:
        return bool(self._writer and not self._writer.is_closing())

    async def send_request(self, msg: Union[str, bytes]):
        if isinstance(msg, str):
            msg = msg.encode()

        self._writer.write(msg + b'\n')
        await self._writer.drain()

    async def drain(self):
        while self.connected:
            # read() does not raise an exception when connection is closed
            # connected status must be checked explicitly later
            recv = await self._reader.read(100)

            # read() returns empty if EOF received
            if not recv:  # pragma: no cover
                raise ConnectionError('EOF received')

            # Send to parser
            self._parser.push(recv.decode())

            # Drain parsed messages
            for msg in self._parser.event_messages():
                await self.on_event(msg)
            for msg in self._parser.data_messages():
                await self.on_response(msg)

    async def close(self):
        with suppress(Exception):
            self._writer.close()
            LOGGER.info(f'{self} closed stream writer')


class SubprocessConnection(StreamConnection):

    def __init__(self,
                 address: str,
                 proc: Popen,
                 reader: asyncio.StreamReader,
                 writer: asyncio.StreamWriter,
                 ) -> None:
        super().__init__(address, reader, writer)
        self._proc = proc

    async def close(self):
        with suppress(Exception):
            self._proc.terminate()
            LOGGER.info(f'{self} terminated subprocess')


async def connect_tcp(host: str, port: int) -> BaseConnection:
    reader, writer = await asyncio.open_connection(host, port)
    return StreamConnection(f'{host}:{port}', reader, writer)


async def connect_subprocess(proc: Popen, address: str) -> BaseConnection:
    host = SUBPROCESS_HOST
    port = SUBPROCESS_PORT
    message = None

    # We just started a subprocess
    # Give it some time to get started and respond to the port
    for _ in range(SUBPROCESS_CONNECT_RETRY_COUNT):
        await asyncio.sleep(SUBPROCESS_CONNECT_INTERVAL_S)

        if proc.poll() is not None:
            raise ChildProcessError(f'Subprocess exited with return code {proc.returncode}')

        try:
            reader, writer = await asyncio.open_connection(host, port)
            return SubprocessConnection(address, proc, reader, writer)

        except OSError as ex:
            message = strex(ex)
            LOGGER.debug(f'Subprocess connection error: {message}')

    # Kill off leftovers
    with suppress(Exception):
        proc.terminate()

    raise ConnectionError(message)


async def connect_simulation(app: web.Application) -> BaseConnection:
    arch = platform.machine()
    binary = SIM_BINARIES.get(arch)
    device_id = app['config']['device_id']

    if not binary:
        raise exceptions.ConnectionImpossible(
            f'No simulator available for architecture {arch}')

    workdir = Path('simulator/').resolve()
    workdir.mkdir(mode=0o777, exist_ok=True)

    proc = Popen(
        [f'../firmware/{binary}', '--device_id', device_id],
        cwd=workdir)
    return await connect_subprocess(proc, binary)


async def connect_serial(address: str) -> BaseConnection:
    proc = Popen([
        '/usr/bin/socat',
        f'tcp-listen:{SUBPROCESS_PORT},reuseaddr,fork',
        f'file:{address},raw,echo=0,b{USB_BAUD_RATE}'
    ])
    return await connect_subprocess(proc, address)


async def discover_tcp(app: web.Application) -> Optional[BaseConnection]:
    try:
        device_id = app['config']['device_id']
        resp = await mdns.discover_one(device_id,
                                       BREWBLOX_DNS_TYPE,
                                       DISCOVERY_DNS_TIMEOUT_S)
        return await connect_tcp(resp.address, resp.port)
    except asyncio.TimeoutError:
        return None


async def discover_serial(app: web.Application) -> Optional[BaseConnection]:
    device_id = app['config']['device_id']
    for port in list_ports.grep(SPARK_DEVICE_REGEX):
        if device_id is None or device_id.lower() == port.serial_number.lower():
            LOGGER.info(f'Discovered {[v for v in port]}')
            return await connect_serial(port.device)
        else:
            LOGGER.info(f'Discarding {[v for v in port]}')
    return None
