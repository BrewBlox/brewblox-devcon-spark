"""
Stream-based connections to the Spark.
The connection itself is always TCP.
For serial and simulation targets, the TCP server is a subprocess.
"""

import asyncio
import platform
from asyncio.subprocess import Process
from contextlib import suppress
from functools import partial
from pathlib import Path
from typing import Optional

from aiohttp import web
from async_timeout import timeout
from brewblox_service import brewblox_logger, strex
from serial.tools import list_ports

from brewblox_devcon_spark import exceptions, mdns
from brewblox_devcon_spark.models import ServiceConfig

from .cbox_parser import ControlboxParser
from .connection_impl import (ConnectionCallbacks, ConnectionImplBase,
                              ConnectionKind_)

LOGGER = brewblox_logger(__name__)

DISCOVERY_DNS_TIMEOUT_S = 20
BREWBLOX_DNS_TYPE = '_brewblox._tcp.local.'
SUBPROCESS_CONNECT_INTERVAL_S = 0.2
SUBPROCESS_CONNECT_TIMEOUT_S = 10
USB_BAUD_RATE = 115200
SIMULATION_CWD = 'simulator/'

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


class StreamConnection(ConnectionImplBase):
    def __init__(self,
                 kind: ConnectionKind_,
                 address: str,
                 callbacks: ConnectionCallbacks):
        super().__init__(kind, address, callbacks)

        self._transport: asyncio.Transport = None
        self._parser = ControlboxParser()

    def connection_made(self, transport: asyncio.Transport):
        self._transport = transport
        self.connected.set()

    def data_received(self, recv: bytes):
        self._parser.push(recv.decode())

        # Drain parsed messages
        for msg in self._parser.event_messages():
            asyncio.create_task(self.on_event(msg))
        for msg in self._parser.data_messages():
            asyncio.create_task(self.on_response(msg))

    def pause_writing(self):  # pragma: no cover
        LOGGER.debug(f'{self} pause_writing')

    def resume_writing(self):  # pragma: no cover
        LOGGER.debug(f'{self} resume_writing')

    def connection_lost(self, ex: Optional[Exception]):
        if ex:
            LOGGER.error(f'Connection closed with error: {strex(ex)}')
        self.disconnected.set()

    async def send_request(self, msg: str):
        self._transport.write(msg.encode() + b'\n')

    async def close(self):
        self._transport.close()


class SubprocessConnection(StreamConnection):  # pragma: no cover

    def __init__(self,
                 kind: ConnectionKind_,
                 address: str,
                 callbacks: ConnectionCallbacks,
                 proc: Process):
        super().__init__(kind, address, callbacks)
        self._proc = proc

    async def close(self):
        with suppress(Exception):
            await super().close()
        with suppress(Exception):
            self._proc.terminate()


async def connect_tcp(app: web.Application,
                      callbacks: ConnectionCallbacks,
                      host: str,
                      port: int,
                      ) -> ConnectionImplBase:
    factory = partial(StreamConnection, 'TCP', f'{host}:{port}', callbacks)
    _, protocol = await asyncio.get_event_loop().create_connection(factory, host, port)
    return protocol


async def connect_subprocess(app: web.Application,
                             callbacks: ConnectionCallbacks,
                             port: int,
                             proc: Process,
                             kind: ConnectionKind_,
                             address: str,
                             ) -> ConnectionImplBase:  # pragma: no cover
    factory = partial(SubprocessConnection, kind, address, callbacks, proc)
    message = None

    # We just started a subprocess
    # Give it some time to get started and respond to the port
    try:
        async with timeout(SUBPROCESS_CONNECT_TIMEOUT_S):
            while True:
                if proc.returncode is not None:
                    raise ChildProcessError(f'Subprocess exited with return code {proc.returncode}')

                try:
                    _, protocol = await asyncio.get_event_loop().create_connection(factory, 'localhost', port)
                    return protocol

                except OSError as ex:
                    message = strex(ex)
                    LOGGER.debug(f'Subprocess connection error: {message}')
                    await asyncio.sleep(SUBPROCESS_CONNECT_INTERVAL_S)

    except asyncio.TimeoutError:
        with suppress(Exception):
            proc.terminate()
        raise ConnectionError(message)


async def connect_simulation(app: web.Application,
                             callbacks: ConnectionCallbacks,
                             ) -> ConnectionImplBase:  # pragma: no cover
    config: ServiceConfig = app['config']
    device_id = config.device_id
    port = config.device_port
    display_ws_port = config.display_ws_port
    arch = platform.machine()
    binary = SIM_BINARIES.get(arch)

    if not binary:
        raise exceptions.ConnectionImpossible(
            f'No simulator available for architecture {arch}')

    binary_path = Path(f'firmware/{binary}').resolve()
    workdir = Path(SIMULATION_CWD).resolve()
    workdir.mkdir(mode=0o777, exist_ok=True)

    proc = await asyncio.create_subprocess_exec(binary_path,
                                                '--device_id', device_id,
                                                '--port', str(port),
                                                '--display_ws_port', str(display_ws_port),
                                                cwd=workdir)
    return await connect_subprocess(app, callbacks, port, proc, 'SIM', binary)


async def connect_usb(app: web.Application,
                      callbacks: ConnectionCallbacks,
                      device_serial: Optional[str] = None,
                      port: Optional[int] = None,
                      ) -> ConnectionImplBase:  # pragma: no cover
    config: ServiceConfig = app['config']
    device_serial = device_serial or config.device_serial
    port = port or config.device_port
    proc = await asyncio.create_subprocess_exec('/usr/bin/socat',
                                                f'tcp-listen:{port},reuseaddr,fork',
                                                f'file:{device_serial},raw,echo=0,b{USB_BAUD_RATE}')

    return await connect_subprocess(app, callbacks, port, proc, 'USB', device_serial)


async def discover_mdns(app: web.Application,
                        callbacks: ConnectionCallbacks,
                        ) -> Optional[ConnectionImplBase]:
    device_id = app['config'].device_id
    try:
        resp = await mdns.discover_one(device_id,
                                       BREWBLOX_DNS_TYPE,
                                       DISCOVERY_DNS_TIMEOUT_S)
        return await connect_tcp(app, callbacks, resp.address, resp.port)
    except asyncio.TimeoutError:
        return None


async def discover_usb(app: web.Application,
                       callbacks: ConnectionCallbacks,
                       ) -> Optional[ConnectionImplBase]:  # pragma: no cover
    config: ServiceConfig = app['config']
    device_id = config.device_id
    for usb_port in list_ports.grep(SPARK_DEVICE_REGEX):
        if device_id is None or device_id.lower() == usb_port.serial_number.lower():
            LOGGER.info(f'Discovered {[v for v in usb_port]}')
            return await connect_usb(app, callbacks, usb_port.device)
        else:
            LOGGER.info(f'Discarding {[v for v in usb_port]}')
    return None
