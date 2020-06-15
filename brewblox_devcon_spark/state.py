"""
Awaitable events for tracking device and network status
"""


import asyncio
import warnings
from dataclasses import asdict, dataclass
from typing import List

from aiohttp import web
from brewblox_service import brewblox_logger, features

LOGGER = brewblox_logger(__name__)


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
    type: str
    address: str
    connection: str
    compatible: bool
    latest: bool
    valid: bool
    service: ServiceInfo
    device: DeviceInfo
    info: List[str]

    autoconnecting: bool
    connect: bool
    handshake: bool
    synchronize: bool


class ServiceState(features.ServiceFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)
        self._address: str = None
        self._simulation: bool = app['config']['simulation']
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
    def connection(self) -> str:
        if not self._address:
            return None
        if self._simulation:
            return 'simulation'
        if ':' in self._address:
            return 'wifi'
        else:
            return 'usb'

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
            'connection': self.connection,
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

    def reset(self):
        self._device = None
        self._info = []


class ServiceEvents(features.ServiceFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)
        self.autoconnecting_ev: asyncio.Event = None
        self.connect_ev: asyncio.Event = None
        self.handshake_ev: asyncio.Event = None
        self.synchronize_ev: asyncio.Event = None
        self.disconnect_ev: asyncio.Event = None

    async def startup(self, app: web.Application):
        self.autoconnecting_ev = asyncio.Event()
        self.connect_ev = asyncio.Event()
        self.handshake_ev = asyncio.Event()
        self.synchronize_ev = asyncio.Event()
        self.disconnect_ev = asyncio.Event()

    async def shutdown(self, app: web.Application):
        pass

    def summary(self) -> dict:
        return {
            'autoconnecting': self.autoconnecting_ev.is_set(),
            'connect': self.connect_ev.is_set(),
            'handshake': self.handshake_ev.is_set(),
            'synchronize': self.synchronize_ev.is_set(),
        }

    async def set_autoconnecting(self, enabled: bool):
        if enabled:
            self.autoconnecting_ev.set()
        else:
            self.autoconnecting_ev.clear()

    async def set_connect(self):
        self.disconnect_ev.clear()
        self.connect_ev.set()

    async def set_handshake(self):
        self.handshake_ev.set()

    async def set_synchronize(self):
        self.synchronize_ev.set()

    async def set_disconnect(self):
        self.connect_ev.clear()
        self.handshake_ev.clear()
        self.synchronize_ev.clear()
        self.disconnect_ev.set()


# Public functions


def setup(app: web.Application):
    features.add(app, ServiceState(app))
    features.add(app, ServiceEvents(app))


def _state(app: web.Application) -> ServiceState:
    return features.get(app, ServiceState)


def _events(app: web.Application) -> ServiceEvents:
    return features.get(app, ServiceEvents)


async def set_autoconnecting(app: web.Application, enabled: bool):
    await _events(app).set_autoconnecting(enabled)


async def set_connect(app: web.Application, address: str):
    _state(app).set_address(address)
    await _events(app).set_connect()


async def set_handshake(app: web.Application, device: DeviceInfo):
    _state(app).set_device(device)
    await _events(app).set_handshake()


async def set_synchronize(app: web.Application):
    await _events(app).set_synchronize()


async def set_disconnect(app: web.Application):
    _state(app).reset()
    await _events(app).set_disconnect()


async def _wait_ev(ev: asyncio.Event, wait: bool) -> bool:
    if not wait:
        return ev.is_set()
    return await ev.wait()


async def wait_autoconnecting(app: web.Application, wait: bool = True) -> bool:
    return await _wait_ev(_events(app).autoconnecting_ev, wait)


async def wait_connect(app: web.Application, wait: bool = True) -> bool:
    return await _wait_ev(_events(app).connect_ev, wait)


async def wait_handshake(app: web.Application, wait: bool = True) -> bool:
    return await _wait_ev(_events(app).handshake_ev, wait)


async def wait_synchronize(app: web.Application, wait: bool = True) -> bool:
    return await _wait_ev(_events(app).synchronize_ev, wait)


async def wait_disconnect(app: web.Application, wait: bool = True) -> bool:
    return await _wait_ev(_events(app).disconnect_ev, wait)


def summary(app: web.Application) -> StateSummary:
    return StateSummary(
        type='Spark',
        **_state(app).summary(),
        **_events(app).summary(),
    )


def summary_dict(app: web.Application) -> dict:
    return asdict(summary(app))
