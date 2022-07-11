"""
Awaitable events for tracking device and network status
"""


import asyncio
import warnings
from functools import partialmethod
from typing import Optional

from aiohttp import web
from brewblox_service import brewblox_logger, features

from brewblox_devcon_spark.models import (DeviceInfo, HandshakeMessage,
                                          ServiceInfo, ServiceStatusInfo)

LOGGER = brewblox_logger(__name__)


class ServiceStatus(features.ServiceFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)
        ini = app['ini']
        config = app['config']

        self.device_address: str = None
        self.connection_kind: str = None

        self.service_info = ServiceInfo(
            firmware_version=ini['firmware_version'],
            proto_version=ini['proto_version'],
            firmware_date=ini['firmware_date'],
            proto_date=ini['proto_date'],
            device_id=config['device_id'] or '',
            name=config['name'],
        )
        self.device_info: DeviceInfo = None
        self.handshake_info: HandshakeInfo = None

        self.enabled_ev: asyncio.Event = None
        self.connected_ev: asyncio.Event = None
        self.acknowledged_ev: asyncio.Event = None
        self.synchronized_ev: asyncio.Event = None
        self.disconnected_ev: asyncio.Event = None
        self.updating_ev: asyncio.Event = None

    async def startup(self, _):
        self.enabled_ev = asyncio.Event()
        self.connected_ev = asyncio.Event()
        self.acknowledged_ev = asyncio.Event()
        self.synchronized_ev = asyncio.Event()
        self.disconnected_ev = asyncio.Event()
        self.updating_ev = asyncio.Event()

    async def shutdown(self, _):
        self.enabled_ev.clear()
        self.connected_ev.clear()
        self.acknowledged_ev.clear()
        self.synchronized_ev.clear()
        self.disconnected_ev.clear()
        self.updating_ev.clear()

    def desc(self) -> StatusDescription:
        return StatusDescription(
            device_address=self.device_address,
            connection_kind=self.connection_kind,
            service_info=self.service_info,
            device_info=self.device_info,
            handshake_info=self.handshake_info,
            is_enabled=self.enabled_ev.is_set(),
            is_connected=self.connected_ev.is_set(),
            is_acknowledged=self.acknowledged_ev.is_set(),
            is_synchronized=self.synchronized_ev.is_set(),
            is_updating=self.updating_ev.is_set(),
        )

    def _set_address(self, address: str):
        simulation = self.app['config']['simulation']
        self.device_address = address

        if not address:
            self.connection_kind = None
        elif simulation:
            self.connection_kind = 'simulation'
        elif ':' in address:
            self.connection_kind = 'wifi'
        else:
            self.connection_kind = 'usb'

    def _set_device(self, device: Optional[DeviceInfo]):
        config = self.app['config']
        service = self.service_info

        if device:
            compatible = service.proto_version == device.proto_version \
                or bool(config['skip_version_check'])
            latest = service.firmware_version == device.firmware_version
            valid = service.device_id == device.device_id \
                or not service.device_id

            if not compatible:
                warnings.warn('Handshake error: firmware incompatible')

            if not valid:
                warnings.warn('Handshake error: invalid device ID')

            self.device_info = device
            self.handshake_info = HandshakeInfo(
                is_compatible_firmware=compatible,
                is_latest_firmware=latest,
                is_valid_device_id=valid,
            )
        else:
            self.device_info = None
            self.handshake_info = None

    def set_enabled(self, enabled: bool):
        if enabled:
            self.enabled_ev.set()
        else:
            self.enabled_ev.clear()

    def set_connected(self, address: str):
        self._set_address(address)

        self.connected_ev.set()
        self.acknowledged_ev.clear()
        self.synchronized_ev.clear()
        self.disconnected_ev.clear()

    def set_acknowledged(self, device: DeviceInfo):
        self._set_device(device)
        self.acknowledged_ev.set()

    def set_synchronized(self):
        self.synchronized_ev.set()

    def set_disconnected(self):
        self._set_address(None)
        self._set_device(None)

        self.connected_ev.clear()
        self.acknowledged_ev.clear()
        self.synchronized_ev.clear()
        self.disconnected_ev.set()

    def set_updating(self):
        self.updating_ev.set()

    async def _wait_ev(self, ev_name: str, wait: bool = True) -> bool:
        ev: asyncio.Event = getattr(self, ev_name)
        if not wait:
            return ev.is_set()
        return await ev.wait()

    wait_enabled = partialmethod(_wait_ev, 'enabled_ev')
    wait_connected = partialmethod(_wait_ev, 'connected_ev')
    wait_acknowledged = partialmethod(_wait_ev, 'acknowledged_ev')
    wait_synchronized = partialmethod(_wait_ev, 'synchronized_ev')
    wait_disconnected = partialmethod(_wait_ev, 'disconnected_ev')
    wait_updating = partialmethod(_wait_ev, 'updating_ev')


def setup(app: web.Application):
    features.add(app, ServiceStatus(app))


def fget(app: web.Application) -> ServiceStatus:
    return features.get(app, ServiceStatus)


# Convenience functions

def set_enabled(app: web.Application, enabled: bool):
    fget(app).set_enabled(enabled)


def set_connected(app: web.Application, address: str):
    fget(app).set_connected(address)


def set_acknowledged(app: web.Application, device: DeviceInfo):
    fget(app).set_acknowledged(device)


def set_synchronized(app: web.Application):
    fget(app).set_synchronized()


def set_disconnected(app: web.Application):
    fget(app).set_disconnected()


def set_updating(app: web.Application):
    fget(app).set_updating()


async def wait_enabled(app: web.Application, wait: bool = True) -> bool:
    return await fget(app).wait_enabled(wait)


async def wait_connected(app: web.Application, wait: bool = True) -> bool:
    return await fget(app).wait_connected(wait)


async def wait_acknowledged(app: web.Application, wait: bool = True) -> bool:
    return await fget(app).wait_acknowledged(wait)


async def wait_synchronized(app: web.Application, wait: bool = True) -> bool:
    return await fget(app).wait_synchronized(wait)


async def wait_disconnected(app: web.Application, wait: bool = True) -> bool:
    return await fget(app).wait_disconnected(wait)


async def wait_updating(app: web.Application, wait: bool = True) -> bool:
    return await fget(app).wait_updating(wait)


def desc(app: web.Application) -> StatusDescription:
    return fget(app).desc()
