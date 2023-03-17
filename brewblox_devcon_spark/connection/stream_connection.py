"""
Stream-based connections to the Spark.
The connection itself is always TCP.
For serial and simulation targets, the TCP server is a subprocess.
"""

import asyncio
import platform
from contextlib import suppress
from functools import partial
from pathlib import Path
from subprocess import Popen
from typing import Optional, Union

from aiohttp import web
from brewblox_service import brewblox_logger, strex
from serial.tools import list_ports

from brewblox_devcon_spark import exceptions, mdns

from .cbox_parser import ControlboxParser
from .connection_impl import ConnectionCallbacks, ConnectionImpl, ConnKind_

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


class StreamConnection(ConnectionImpl):
    def __init__(self,
                 kind: ConnKind_,
                 address: str,
                 callbacks: ConnectionCallbacks
                 ) -> None:
        super().__init__(kind, address, callbacks)

        self._transport: asyncio.Transport = None
        self._active = asyncio.Event()
        self._parser = ControlboxParser()

    def connection_made(self, transport: asyncio.Transport):
        self._transport = transport
        self.connected.set()
        self._active.set()

    def data_received(self, recv: bytes):
        self._parser.push(recv.decode())

        # Drain parsed messages
        for msg in self._parser.event_messages():
            asyncio.create_task(self.on_event(msg))
        for msg in self._parser.data_messages():
            asyncio.create_task(self.on_response(msg))

    def pause_writing(self):
        self._active.clear()

    def resume_writing(self):
        self._active.set()

    def connection_lost(self, ex: Optional[Exception]):
        if ex:
            LOGGER.error(f'Connection closed with error: {strex(ex)}')
        self.disconnected.set()

    async def send_request(self, msg: Union[str, bytes]):
        if isinstance(msg, str):
            msg = msg.encode()

        # Maybe?
        # await self._active.wait()
        self._transport.write(msg + b'\n')

    async def close(self):
        if self._transport:
            self._transport.close()


class SubprocessConnection(StreamConnection):

    def __init__(self,
                 kind: ConnKind_,
                 address: str,
                 callbacks: ConnectionCallbacks,
                 proc: Popen) -> None:
        super().__init__(kind, address, callbacks)
        self._proc = proc

    async def close(self):
        with suppress(Exception):
            await super().close()
            self._proc.terminate()
            LOGGER.info(f'{self} terminated subprocess')


async def connect_tcp(host: str, port: int, callbacks: ConnectionCallbacks) -> ConnectionImpl:
    # reader, writer = await asyncio.open_connection(host, port)
    # return StreamConnection('TCP', f'{host}:{port}', reader, writer)
    factory = partial(StreamConnection, 'TCP', f'{host}:{port}', callbacks)
    _, protocol = asyncio.get_event_loop().create_connection(factory, host, port)
    return protocol


async def connect_subprocess(proc: Popen,
                             kind: ConnKind_,
                             address: str,
                             callbacks: ConnectionCallbacks,
                             ) -> ConnectionImpl:
    host = SUBPROCESS_HOST
    port = SUBPROCESS_PORT
    message = None

    # We just started a subprocess
    # Give it some time to get started and respond to the port
    for _ in range(SUBPROCESS_CONNECT_RETRY_COUNT):
        if proc.poll() is not None:
            raise ChildProcessError(f'Subprocess exited with return code {proc.returncode}')

        try:
            # reader, writer = await asyncio.open_connection(host, port)
            # return SubprocessConnection(kind, address, proc, reader, writer)
            factory = partial(SubprocessConnection, kind, address, callbacks, proc)
            _, protocol = asyncio.get_event_loop().create_connection(factory, host, port)
            return protocol

        except OSError as ex:
            message = strex(ex)
            LOGGER.debug(f'Subprocess connection error: {message}')
            await asyncio.sleep(SUBPROCESS_CONNECT_INTERVAL_S)

    # Kill off leftovers
    with suppress(Exception):
        proc.terminate()

    raise ConnectionError(message)


async def connect_simulation(app: web.Application, callbacks: ConnectionCallbacks) -> ConnectionImpl:
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
    return await connect_subprocess(proc, 'SIM', binary, callbacks)


async def connect_serial(devfile: str, callbacks: ConnectionCallbacks) -> ConnectionImpl:
    proc = Popen([
        '/usr/bin/socat',
        f'tcp-listen:{SUBPROCESS_PORT},reuseaddr,fork',
        f'file:{devfile},raw,echo=0,b{USB_BAUD_RATE}'
    ])
    return await connect_subprocess(proc, 'USB', devfile, callbacks)


async def discover_tcp(app: web.Application, callbacks: ConnectionCallbacks) -> Optional[ConnectionImpl]:
    try:
        device_id = app['config']['device_id']
        resp = await mdns.discover_one(device_id,
                                       BREWBLOX_DNS_TYPE,
                                       DISCOVERY_DNS_TIMEOUT_S)
        return await connect_tcp(resp.address, resp.port, callbacks)
    except asyncio.TimeoutError:
        return None


async def discover_serial(app: web.Application, callbacks: ConnectionCallbacks) -> Optional[ConnectionImpl]:
    device_id = app['config']['device_id']
    for port in list_ports.grep(SPARK_DEVICE_REGEX):
        if device_id is None or device_id.lower() == port.serial_number.lower():
            LOGGER.info(f'Discovered {[v for v in port]}')
            return await connect_serial(port.device, callbacks)
        else:
            LOGGER.info(f'Discarding {[v for v in port]}')
    return None
