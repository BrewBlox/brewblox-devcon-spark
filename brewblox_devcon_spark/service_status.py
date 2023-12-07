"""
Awaitable events for tracking device and network status
"""


import asyncio
import logging
import warnings
from contextvars import ContextVar

from . import utils
from .models import (ConnectionKind_, ControllerDescription, DeviceDescription,
                     FirmwareDescription, ServiceDescription,
                     ServiceStatusDescription)

LOGGER = logging.getLogger(__name__)
CV: ContextVar['ServiceStatus'] = ContextVar('service_status.ServiceStatus')


class ServiceStatus:

    def __init__(self):
        config = utils.get_config()
        fw_config = utils.get_fw_config()

        service_desc = ServiceDescription(
            name=config.name,
            firmware=FirmwareDescription(
                firmware_version=fw_config.firmware_version,
                proto_version=fw_config.proto_version,
                firmware_date=fw_config.firmware_date,
                proto_date=fw_config.proto_date,
            ),
            device=DeviceDescription(
                device_id=config.device_id or '',
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

        self.enabled_ev = asyncio.Event()
        self.connected_ev = asyncio.Event()
        self.acknowledged_ev = asyncio.Event()
        self.synchronized_ev = asyncio.Event()
        self.disconnected_ev = asyncio.Event()
        self.updating_ev = asyncio.Event()

    def desc(self) -> ServiceStatusDescription:
        return self.status_desc.model_copy()

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

        LOGGER.info(f'>>> CONNECTED ({connection_kind})')
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

        config = utils.get_config()
        service = self.status_desc.service

        wildcard_id = not service.device.device_id
        compatible_firmware = service.firmware.proto_version == controller.firmware.proto_version \
            or bool(config.skip_version_check)
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


def setup():
    CV.set(ServiceStatus())
