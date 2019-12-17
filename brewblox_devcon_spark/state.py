"""
Awaitable events for tracking device and network status
"""


import asyncio
import warnings
from dataclasses import dataclass
from typing import List

from aiohttp import web
from brewblox_service import brewblox_logger, features

LOGGER = brewblox_logger(__name__)


def setup(app: web.Application):
    features.add(app, ServiceStatus(app))
    features.add(app, ServiceEvents(app))


def get_status(app: web.Application) -> 'ServiceStatus':
    return features.get(app, ServiceStatus)


def get_events(app: web.Application) -> 'ServiceEvents':
    return features.get(app, ServiceEvents)


@dataclass
class SharedInfo:
    firmware_version: str
    proto_version: str
    firmware_date: str
    proto_date: str
    device_id: str

    def __post_init__(self):
        if self.device_id is not None:
            self.device_id = self.device_id.lower()


@dataclass
class ServiceInfo(SharedInfo):
    pass


@dataclass
class DeviceInfo(SharedInfo):
    system_version: str
    platform: str
    reset_reason: str


@dataclass
class StateSummary:
    address: str
    compatible: bool
    latest: bool
    valid: bool
    service: ServiceInfo
    device: DeviceInfo
    info: List[str]

    connect: bool
    handshake: bool
    synchronize: bool


class ServiceStatus(features.ServiceFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)
        self._address: str = None
        self._compatible: bool = True  # until proven otherwise
        self._latest: bool = True
        self._valid: bool = True

        self._service: ServiceInfo = None
        self._device: DeviceInfo = None
        self._info: List[str] = []

    async def startup(self, _):
        pass

    async def shutdown(self, _):
        pass

    @property
    def address(self) -> str:
        return self._address

    @property
    def compatible(self) -> bool:
        return self._compatible

    @property
    def latest(self) -> bool:
        return self._latest

    @property
    def valid(self) -> bool:
        return self._valid

    @property
    def info(self) -> List[str]:
        return self._info

    @property
    def device(self) -> DeviceInfo:
        return self._device

    @property
    def service(self) -> ServiceInfo:
        return self._service

    def summary(self) -> dict:
        return {
            'address': self.address,
            'compatible': self.compatible,
            'latest': self.latest,
            'valid': self.valid,
            'service': self.service,
            'device': self.device,
            'info': self.info,
        }

    def set_address(self, address: str):
        self._address = address

    def set_device(self, device: DeviceInfo):
        config = self.app['config']
        ini = self.app['ini']
        service = ServiceInfo(
            ini['firmware_version'],
            ini['proto_version'],
            ini['firmware_date'],
            ini['proto_date'],
            config['device_id'],
        )

        self._service = service
        self._device = device

        self._compatible = bool(config['skip_version_check']) or service.proto_version == device.proto_version
        self._latest = service.firmware_version == device.firmware_version
        self._valid = not service.device_id or service.device_id == device.device_id

        if not self._compatible:
            warnings.warn('Handshake error: firmware incompatible')

        if not self._valid:
            warnings.warn('Handshake error: invalid device ID')

        self._info = [
            f'Firmware version (service): {service.firmware_version}',
            f'Firmware version (controller): {device.firmware_version}',
            f'Firmware date (service): {service.firmware_date}',
            f'Firmware date (controller): {device.firmware_date}',
            f'Protocol version (service): {service.proto_version}',
            f'Protocol version (controller): {device.proto_version}',
            f'Protocol date (service): {service.proto_date}',
            f'Protocol date (controller): {device.proto_date}',
            f'System version (controller): {device.system_version}',
            f'Desired device ID (service): {service.device_id}',
            f'Actual device ID (controller): {device.device_id}',
        ]

    def reset(self):
        self._device = None
        self._info = []


class ServiceEvents(features.ServiceFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)
        self.connect_ev: asyncio.Event = None
        self.handshake_ev: asyncio.Event = None
        self.synchronize_ev: asyncio.Event = None
        self.disconnect_ev: asyncio.Event = None

    async def startup(self, app: web.Application):
        self.connect_ev = asyncio.Event()
        self.handshake_ev = asyncio.Event()
        self.synchronize_ev = asyncio.Event()
        self.disconnect_ev = asyncio.Event()

    async def shutdown(self, app: web.Application):
        pass

    def summary(self) -> dict:
        return {
            'connect': self.connect_ev.is_set(),
            'handshake': self.handshake_ev.is_set(),
            'synchronize': self.synchronize_ev.is_set(),
        }

    async def on_connect(self):
        self.disconnect_ev.clear()
        self.connect_ev.set()

    async def on_handshake(self):
        self.handshake_ev.set()

    async def on_synchronize(self):
        self.synchronize_ev.set()

    async def on_disconnect(self):
        self.connect_ev.clear()
        self.handshake_ev.clear()
        self.synchronize_ev.clear()
        self.disconnect_ev.set()


# Public functions

async def wait_connect(app: web.Application) -> bool:
    return await get_events(app).connect_ev.wait()


async def wait_handshake(app: web.Application) -> bool:
    return await get_events(app).handshake_ev.wait()


async def wait_synchronize(app: web.Application, wait: bool = True) -> bool:
    if not wait:
        return get_events(app).synchronize_ev.is_set()
    return await get_events(app).synchronize_ev.wait()


async def wait_disconnect(app: web.Application) -> bool:
    await get_events(app).disconnect_ev.wait()


async def on_connect(app: web.Application, address: str):
    get_status(app).set_address(address)
    await get_events(app).on_connect()


async def on_handshake(app: web.Application, device: DeviceInfo):
    get_status(app).set_device(device)
    await get_events(app).on_handshake()


async def on_synchronize(app: web.Application):
    await get_events(app).on_synchronize()


async def on_disconnect(app: web.Application):
    get_status(app).reset()
    await get_events(app).on_disconnect()


def summary(app: web.Application) -> StateSummary:
    return StateSummary(
        **get_status(app).summary(),
        **get_events(app).summary(),
    )
