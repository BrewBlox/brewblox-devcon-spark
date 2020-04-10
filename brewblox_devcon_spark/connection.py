"""
Creating a new connection to the Spark controller
"""

import asyncio
from collections import namedtuple
from typing import Any, Iterable, Iterator, Tuple

from aiohttp import ClientResponseError, web
from brewblox_service import brewblox_logger, http, strex
from serial.tools import list_ports
from serial_asyncio import open_serial_connection

from brewblox_devcon_spark import exceptions

PortType_ = Any
ConnectionResult_ = Tuple[Any, asyncio.StreamReader, asyncio.StreamWriter]

DeviceMatch = namedtuple('DeviceMatch', ['id', 'desc', 'hwid'])

LOGGER = brewblox_logger(__name__)

DEFAULT_BAUD_RATE = 115200
DISCOVER_INTERVAL_S = 10
DISCOVERY_RETRY_COUNT = 5
DNS_DISCOVER_TIMEOUT_S = 20

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
    LOGGER.info(f'Starting device discovery, type={discovery_type}')

    for i in range(DISCOVERY_RETRY_COUNT):
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

    LOGGER.error('Device discovery failed. Exiting now.')
    raise web.GracefulExit()


async def discover_serial(app: web.Application) -> ConnectionResult_:
    id = app['config']['device_id']
    try:
        address = detect_device(id)
        return await connect_serial(address)
    except exceptions.ConnectionImpossible:
        return None


async def discover_tcp(app: web.Application) -> ConnectionResult_:
    config = app['config']
    id = config['device_id']
    mdns_host = config['mdns_host']
    mdns_port = config['mdns_port']
    try:
        retv = await asyncio.wait_for(
            http.session(app).post(f'http://{mdns_host}:{mdns_port}/mdns/discover',
                                   json={'id': id}),
            DNS_DISCOVER_TIMEOUT_S
        )
        resp = await retv.json()
        host, port = resp['host'], resp['port']
        return await connect_tcp(host, port)

    except TimeoutError:  # pragma: no cover
        return None

    except ClientResponseError as ex:
        LOGGER.info(f'Error connecting mDNS discovery service: {strex(ex)}')
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
