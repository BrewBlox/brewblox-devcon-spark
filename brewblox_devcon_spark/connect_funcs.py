"""
Creating a new connection to the Spark controller
"""

import asyncio
import platform
import subprocess
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from aiohttp import web
from brewblox_service import brewblox_logger, strex
from serial.tools import list_ports

from brewblox_devcon_spark import exceptions, mdns

LOGGER = brewblox_logger(__name__)

USB_BAUD_RATE = 115200
SUBPROCESS_HOST = 'localhost'
SUBPROCESS_PORT = 8332
SUBPROCESS_CONNECT_INTERVAL_S = 1
SUBPROCESS_CONNECT_RETRY_COUNT = 10
DISCOVERY_INTERVAL_S = 10
DISCOVERY_RETRY_COUNT = 5
DISCOVERY_DNS_TIMEOUT_S = 20
BREWBLOX_DNS_TYPE = '_brewblox._tcp.local.'

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


@dataclass(frozen=True)
class ConnectionResult:
    host: str
    port: int
    address: str
    process: Optional[subprocess.Popen]
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter


class DiscoveryAbortedError(Exception):
    def __init__(self, reboot_required: bool, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.reboot_required = reboot_required


async def connect(app: web.Application) -> ConnectionResult:
    config = app['config']

    simulation = config['simulation']
    device_serial = config['device_serial']
    device_host = config['device_host']
    device_port = config['device_port']

    if simulation:
        return await connect_simulation(app)
    if device_serial:
        return await connect_serial(device_serial)
    elif device_host:
        return await connect_tcp(device_host, device_port)
    else:
        return await connect_discovered(app)


async def connect_subprocess(proc: subprocess.Popen, address: str) -> ConnectionResult:
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
            return ConnectionResult(
                host=host,
                port=port,
                address=address,
                process=proc,
                reader=reader,
                writer=writer
            )
        except OSError as ex:
            message = strex(ex)
            LOGGER.debug(f'Subprocess connection error: {message}')

    # Kill off leftovers
    with suppress(Exception):
        proc.terminate()

    raise ConnectionError(message)


async def connect_simulation(app: web.Application) -> ConnectionResult:
    arch = platform.machine()
    binary = SIM_BINARIES.get(arch)
    device_id = app['config']['device_id']

    if not binary:
        raise exceptions.ConnectionImpossible(
            f'No simulator available for architecture {arch}')

    workdir = Path('simulator/').resolve()
    workdir.mkdir(mode=0o777, exist_ok=True)
    workdir.joinpath('device_key.der').touch(mode=0o777, exist_ok=True)
    workdir.joinpath('server_key.der').touch(mode=0o777, exist_ok=True)
    workdir.joinpath('eeprom.bin').touch(mode=0o777, exist_ok=True)

    proc = subprocess.Popen(
        [f'../firmware-bin/binaries/{binary}', '--device_id', device_id],
        cwd=workdir)
    return await connect_subprocess(proc, binary)


async def connect_serial(address: str) -> ConnectionResult:
    proc = subprocess.Popen([
        '/usr/bin/socat',
        f'tcp-listen:{SUBPROCESS_PORT},reuseaddr,fork',
        f'file:{address},raw,echo=0,b{USB_BAUD_RATE}'
    ])
    return await connect_subprocess(proc, address)


async def connect_tcp(host: str, port: int) -> ConnectionResult:
    reader, writer = await asyncio.open_connection(host, port)
    return ConnectionResult(
        host=host,
        port=port,
        address=f'{host}:{port}',
        process=None,
        reader=reader,
        writer=writer
    )


async def connect_discovered(app: web.Application) -> ConnectionResult:
    discovery_type = app['config']['discovery']
    LOGGER.info(f'Discovering devices... ({discovery_type})')

    for _ in range(DISCOVERY_RETRY_COUNT):
        if discovery_type in ['all', 'usb']:
            result = await connect_discovered_serial(app)
            if result:
                return result

        if discovery_type in ['all', 'wifi']:
            result = await connect_discovered_tcp(app)
            if result:
                return result

        await asyncio.sleep(DISCOVERY_INTERVAL_S)

    # Newly connected USB devices are only detected after a container restart.
    # This restriction does not apply to Wifi.
    # We only have to periodically restart the service if USB is a valid type.
    reboot_required = discovery_type in ['all', 'usb']
    raise DiscoveryAbortedError(reboot_required)


async def connect_discovered_serial(app: web.Application) -> Optional[ConnectionResult]:
    device_id = app['config']['device_id']
    for port in list_ports.grep(SPARK_DEVICE_REGEX):
        if device_id is None or device_id.lower() == port.serial_number.lower():
            LOGGER.info(f'Discovered {[v for v in port]}')
            return await connect_serial(port.device)
        else:
            LOGGER.info(f'Discarding {[v for v in port]}')
    return None


async def connect_discovered_tcp(app: web.Application) -> Optional[ConnectionResult]:
    try:
        device_id = app['config']['device_id']
        resp = await mdns.discover_one(device_id,
                                       BREWBLOX_DNS_TYPE,
                                       DISCOVERY_DNS_TIMEOUT_S)
        return await connect_tcp(resp[0], resp[1])
    except asyncio.TimeoutError:
        return None
