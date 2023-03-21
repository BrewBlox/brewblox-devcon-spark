"""
Awaitable events for tracking device and network status
"""


import asyncio
import warnings

from aiohttp import web
from brewblox_service import brewblox_logger, features

from brewblox_devcon_spark.models import (ConnectionKind_,
                                          ControllerDescription,
                                          DeviceDescription,
                                          FirmwareDescription, ServiceConfig,
                                          ServiceDescription,
                                          ServiceFirmwareIni,
                                          ServiceStatusDescription)

LOGGER = brewblox_logger(__name__)


class ServiceStatus(features.ServiceFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)
        ini: ServiceFirmwareIni = app['ini']
        config: ServiceConfig = app['config']

        service_desc = ServiceDescription(
            name=config['name'],
            firmware=FirmwareDescription(
                firmware_version=ini['firmware_version'],
                proto_version=ini['proto_version'],
                firmware_date=ini['firmware_date'],
                proto_date=ini['proto_date'],
            ),
            device=DeviceDescription(
                device_id=config['device_id'] or '',
            ),
        )

        self.status_desc = ServiceStatusDescription(
            enabled=False,
            service=service_desc,
            controller=None,
            address=None,
            connection_kind=None,
            connection_status='DISCONNECTED',
            firmware_error=None,
            identity_error=None,
        )

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

    def desc(self) -> ServiceStatusDescription:
        return self.status_desc.copy()

    def set_enabled(self, enabled: bool):
        self.status_desc.enabled = enabled

        if enabled:
            self.enabled_ev.set()
        else:
            self.enabled_ev.clear()

    def set_connected(self,
                      connection_kind: ConnectionKind_,
                      address: str):
        self.status_desc.address = address
        self.status_desc.connection_kind = connection_kind
        self.status_desc.connection_status = 'CONNECTED'

        LOGGER.info('>>> CONNECTED')
        self.connected_ev.set()
        self.acknowledged_ev.clear()
        self.synchronized_ev.clear()
        self.disconnected_ev.clear()

    def set_acknowledged(self, controller: ControllerDescription):
        if self.synchronized_ev.is_set():
            # Do not revert to acknowledged if we're already synchronized.
            # For there to be a meaningful change,
            # there must have been a disconnect first.
            return

        config: ServiceConfig = self.app['config']
        service = self.status_desc.service

        wildcard_id = not service.device.device_id
        compatible_firmware = service.firmware.proto_version == controller.firmware.proto_version \
            or bool(config['skip_version_check'])
        matching_firmware = service.firmware.firmware_version == controller.firmware.firmware_version
        compatible_identity = service.device.device_id == controller.device.device_id \
            or wildcard_id

        if not compatible_firmware:
            warnings.warn('Handshake error: incompatible firmware')

        if not compatible_identity:
            warnings.warn('Handshake error: incompatible device ID')

        # determine firmware_error
        if not compatible_firmware:
            firmware_error = 'INCOMPATIBLE'
        elif not matching_firmware:
            firmware_error = 'MISMATCHED'
        else:
            firmware_error = None

        # determine identity_error
        if not compatible_identity:
            identity_error = 'INCOMPATIBLE'
        elif wildcard_id:
            identity_error = 'WILDCARD_ID'
        else:
            identity_error = None

        self.status_desc.connection_status = 'ACKNOWLEDGED'
        self.status_desc.controller = controller
        self.status_desc.firmware_error = firmware_error
        self.status_desc.identity_error = identity_error

        LOGGER.info('>>> ACKNOWLEDGED')
        self.acknowledged_ev.set()

    def set_synchronized(self):
        if not self.acknowledged_ev.is_set():
            raise RuntimeError('Failed to set synchronized status: '
                               'service is not acknowledged')

        self.status_desc.connection_status = 'SYNCHRONIZED'

        LOGGER.info('>>> SYNCHRONIZED')
        self.synchronized_ev.set()

    def set_updating(self):
        self.status_desc.connection_status = 'UPDATING'

        LOGGER.info('>>> UPDATING')
        self.updating_ev.set()

    def set_disconnected(self):
        self.status_desc.controller = None
        self.status_desc.address = None
        self.status_desc.connection_kind = None
        self.status_desc.connection_status = 'DISCONNECTED'
        self.status_desc.firmware_error = None
        self.status_desc.identity_error = None

        LOGGER.info('>>> DISCONNECTED')
        self.connected_ev.clear()
        self.acknowledged_ev.clear()
        self.synchronized_ev.clear()
        self.updating_ev.clear()
        self.disconnected_ev.set()


def setup(app: web.Application):
    features.add(app, ServiceStatus(app))


def fget(app: web.Application) -> ServiceStatus:
    return features.get(app, ServiceStatus)


def desc(app: web.Application) -> ServiceStatusDescription:
    return fget(app).desc()


def set_enabled(app: web.Application, enabled: bool):
    fget(app).set_enabled(enabled)


def set_connected(app: web.Application,
                  kind: ConnectionKind_,
                  address: str):
    fget(app).set_connected(kind, address)


def set_acknowledged(app: web.Application,
                     controller: ControllerDescription):
    fget(app).set_acknowledged(controller)


def set_synchronized(app: web.Application):
    fget(app).set_synchronized()


def set_updating(app: web.Application):
    fget(app).set_updating()


def set_disconnected(app: web.Application):
    fget(app).set_disconnected()


def is_enabled(app: web.Application) -> bool:
    return fget(app).enabled_ev.is_set()


def is_connected(app: web.Application) -> bool:
    return fget(app).connected_ev.is_set()


def is_acknowledged(app: web.Application) -> bool:
    return fget(app).acknowledged_ev.is_set()


def is_synchronized(app: web.Application) -> bool:
    return fget(app).synchronized_ev.is_set()


def is_disconnected(app: web.Application) -> bool:
    return fget(app).disconnected_ev.is_set()


def is_updating(app: web.Application) -> bool:
    return fget(app).updating_ev.is_set()


async def wait_enabled(app: web.Application) -> bool:
    return await fget(app).enabled_ev.wait()


async def wait_connected(app: web.Application) -> bool:
    return await fget(app).connected_ev.wait()


async def wait_acknowledged(app: web.Application) -> bool:
    return await fget(app).acknowledged_ev.wait()


async def wait_synchronized(app: web.Application) -> bool:
    return await fget(app).synchronized_ev.wait()


async def wait_updating(app: web.Application) -> bool:
    return await fget(app).updating_ev.wait()


async def wait_disconnected(app: web.Application) -> bool:
    return await fget(app).disconnected_ev.wait()
