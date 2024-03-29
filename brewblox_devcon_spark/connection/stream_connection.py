"""
Stream-based connections to the Spark.
The connection itself is always TCP.
For serial and simulation targets, the TCP server is a subprocess.
"""
import asyncio
import logging
import os
import platform
import signal
from asyncio.subprocess import Process
from contextlib import suppress
from functools import partial
from pathlib import Path

from serial.tools import list_ports

from .. import exceptions, mdns, utils
from .cbox_parser import CboxParser
from .connection_impl import (ConnectionCallbacks, ConnectionImplBase,
                              ConnectionKind_)

BREWBLOX_DNS_TYPE = '_brewblox._tcp.local.'
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

LOGGER = logging.getLogger(__name__)


class StreamConnection(ConnectionImplBase):
    def __init__(self,
                 kind: ConnectionKind_,
                 address: str,
                 callbacks: ConnectionCallbacks):
        super().__init__(kind, address, callbacks)

        self._transport: asyncio.Transport = None
        self._parser = CboxParser()

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

    def connection_lost(self, ex: Exception | None):
        if ex:
            LOGGER.error(f'Connection closed with error: {utils.strex(ex)}')
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
            os.killpg(os.getpgid(self._proc.pid), signal.SIGTERM)
            await self._proc.wait()


async def connect_tcp(callbacks: ConnectionCallbacks,
                      host: str,
                      port: int,
                      ) -> ConnectionImplBase:
    factory = partial(StreamConnection, 'TCP', f'{host}:{port}', callbacks)
    _, protocol = await asyncio.get_event_loop().create_connection(factory, host, port)
    return protocol


async def connect_subprocess(callbacks: ConnectionCallbacks,
                             port: int,
                             proc: Process,
                             kind: ConnectionKind_,
                             address: str,
                             ) -> ConnectionImplBase:  # pragma: no cover
    config = utils.get_config()
    loop = asyncio.get_running_loop()
    factory = partial(SubprocessConnection, kind, address, callbacks, proc)
    errors: set[str] = set()

    # We just started a subprocess
    # Give it some time to get started and respond to the port
    try:
        async with asyncio.timeout(config.subprocess_connect_timeout.total_seconds()):
            while True:
                if proc.returncode is not None:
                    raise ChildProcessError(f'Subprocess exited with return code {proc.returncode}')

                try:
                    _, protocol = await loop.create_connection(factory, 'localhost', port)
                    return protocol

                except OSError as ex:
                    errors.add(utils.strex(ex))
                    await asyncio.sleep(config.subprocess_connect_interval.total_seconds())

    except asyncio.TimeoutError:
        with suppress(Exception):
            proc.terminate()
        raise ConnectionError(str(errors))


async def connect_simulation(callbacks: ConnectionCallbacks) -> ConnectionImplBase:  # pragma: no cover
    config = utils.get_config()
    arch = platform.machine()
    binary = SIM_BINARIES.get(arch)

    if not binary:
        raise exceptions.ConnectionImpossible(
            f'No simulator available for architecture {arch}')

    binary_path = Path(f'firmware/{binary}').resolve()
    workdir = config.simulation_workdir.resolve()
    workdir.mkdir(mode=0o777, exist_ok=True)

    proc = await asyncio.create_subprocess_exec(binary_path,
                                                '--device_id', config.device_id,
                                                '--port', str(config.simulation_port),
                                                '--display_ws_port', str(config.simulation_display_port),
                                                cwd=workdir,
                                                preexec_fn=os.setsid,
                                                shell=False)
    return await connect_subprocess(callbacks, config.simulation_port, proc, 'SIM', binary)


async def connect_usb(callbacks: ConnectionCallbacks,
                      device_serial: str | None = None,
                      ) -> ConnectionImplBase:  # pragma: no cover
    config = utils.get_config()
    device_serial = device_serial or config.device_serial
    proc = await asyncio.create_subprocess_exec('/usr/bin/socat',
                                                f'tcp-listen:{config.device_port},reuseaddr,fork',
                                                f'file:{device_serial},raw,echo=0,b{USB_BAUD_RATE}',
                                                preexec_fn=os.setsid,
                                                shell=False)

    return await connect_subprocess(callbacks, config.device_port, proc, 'USB', device_serial)


async def discover_mdns(callbacks: ConnectionCallbacks) -> ConnectionImplBase | None:
    config = utils.get_config()
    try:
        resp = await mdns.discover_one(config.device_id,
                                       BREWBLOX_DNS_TYPE,
                                       config.discovery_timeout_mdns)
        return await connect_tcp(callbacks, resp.address, resp.port)
    except asyncio.TimeoutError:
        return None


async def discover_usb(callbacks: ConnectionCallbacks) -> ConnectionImplBase | None:  # pragma: no cover
    config = utils.get_config()
    for usb_port in list_ports.grep(SPARK_DEVICE_REGEX):
        if config.device_id is None or config.device_id.lower() == usb_port.serial_number.lower():
            LOGGER.info(f'Discovered {[v for v in usb_port]}')
            return await connect_usb(callbacks, usb_port.device)
        else:
            LOGGER.info(f'Discarding {[v for v in usb_port]}')
    return None
