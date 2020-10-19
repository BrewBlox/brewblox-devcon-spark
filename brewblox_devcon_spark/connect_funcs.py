"""
Creating a new connection to the Spark controller
"""

import asyncio
from collections import namedtuple
from typing import Any, Iterable, Iterator, Tuple

from aiohttp import web
from brewblox_service import brewblox_logger
from serial.tools import list_ports
from serial_asyncio import open_serial_connection

from brewblox_devcon_spark import exceptions, mdns

PortType_ = Any
ConnectionResult_ = Tuple[Any, asyncio.StreamReader, asyncio.StreamWriter]

DeviceMatch = namedtuple('DeviceMatch', ['id', 'desc', 'hwid'])

LOGGER = brewblox_logger(__name__)

DEFAULT_BAUD_RATE = 115200
DISCOVER_INTERVAL_S = 10
DISCOVERY_RETRY_COUNT = 5
DNS_DISCOVER_TIMEOUT_S = 20
BREWBLOX_DNS_TYPE = '_brewblox._tcp.local.'

KNOWN_DEVICES = {
    DeviceMatch(
        id='Particle Photon',
        desc=r'.*Photon.*',
        hwid=r'USB VID\:PID=2B04\:C006.*'),
    DeviceMatch(
        id='Particle P1',
        desc=r'.*P1.*',
        hwid=r'USB VID\:PID=2B04\:C008.*'),
}


class DiscoveryAbortedError(Exception):
    def __init__(self, reboot_required: bool, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.reboot_required = reboot_required


async def connect(app: web.Application) -> ConnectionResult_:
    config = app['config']

    device_serial = config['device_serial']
    device_host = config['device_host']
    device_port = config['device_port']

    if device_serial:
        return await connect_serial(device_serial)
    elif device_host:
        return await connect_tcp(device_host, device_port)
    else:
        return await connect_discovered(app)


async def connect_serial(address: str) -> ConnectionResult_:
    reader, writer = await open_serial_connection(url=address, baudrate=DEFAULT_BAUD_RATE)
    writer.transport.serial.rts = False
    writer.transport.set_write_buffer_limits(high=255)  # receiver RX buffer is 256, so limit send buffer to 255
    return address, reader, writer


async def connect_tcp(host: str, port: int) -> ConnectionResult_:
    reader, writer = await asyncio.open_connection(host, port)
    return f'{host}:{port}', reader, writer


async def connect_discovered(app: web.Application) -> ConnectionResult_:
    discovery_type = app['config']['discovery']
    LOGGER.info(f'Discovering devices... ({discovery_type})')

    for _ in range(DISCOVERY_RETRY_COUNT):
        if discovery_type in ['all', 'usb']:
            result = await discover_serial(app)
            if result:
                LOGGER.info(f'discovered usb {result[0]}')
                return result

        if discovery_type in ['all', 'wifi']:
            result = await discover_tcp(app)
            if result:
                LOGGER.info(f'discovered wifi {result[0]}')
                return result

        await asyncio.sleep(DISCOVER_INTERVAL_S)

    # Newly connected USB devices are only detected after a container restart.
    # This restriction does not apply to Wifi.
    # We only have to periodically restart the service if USB is a valid type.
    reboot_required = discovery_type in ['all', 'usb']
    raise DiscoveryAbortedError(reboot_required)


async def discover_serial(app: web.Application) -> ConnectionResult_:
    id = app['config']['device_id']
    try:
        address = detect_device(id)
        return await connect_serial(address)
    except exceptions.ConnectionImpossible:
        return None


async def discover_tcp(app: web.Application) -> ConnectionResult_:
    try:
        id = app['config']['device_id']
        resp = await mdns.discover_one(id,
                                       BREWBLOX_DNS_TYPE,
                                       DNS_DISCOVER_TIMEOUT_S)
        return await connect_tcp(resp[0], resp[1])
    except asyncio.TimeoutError:
        return None


def all_ports() -> Iterable[PortType_]:
    return tuple(list_ports.comports())


def recognized_ports(
    allowed: Iterable[DeviceMatch] = KNOWN_DEVICES,
    serial_number: str = None
) -> Iterator[PortType_]:

    # Construct a regex OR'ing all allowed hardware ID matches
    # Example result: (?:HWID_REGEX_ONE|HWID_REGEX_TWO)
    matcher = f'(?:{"|".join([dev.hwid for dev in allowed])})'

    for port in list_ports.grep(matcher):
        if serial_number is None or serial_number.lower() == port.serial_number.lower():
            yield port


def detect_device(device_id: str = None) -> str:
    try:
        port = next(recognized_ports(serial_number=device_id))
        LOGGER.info(f'Automatically detected {[v for v in port]}')
        return port.device
    except StopIteration:
        raise exceptions.ConnectionImpossible(
            f'Could not find recognized device. Known={[{v for v in p} for p in all_ports()]}')
