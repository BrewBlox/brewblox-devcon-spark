"""
Awaitable events for tracking device and network status
"""


import asyncio
import logging
from contextvars import ContextVar
from typing import Literal

from . import exceptions, utils
from .models import (ConnectionKind_, ControllerDescription, DeviceDescription,
                     FirmwareDescription, ServiceDescription,
                     StatusDescription)

LOGGER = logging.getLogger(__name__)
CV: ContextVar['StateMachine'] = ContextVar('state_machine.StateMachine')


class StateMachine:

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

        self._status_desc = StatusDescription(
            enabled=False,
            service=service_desc,
            controller=None,
            address=None,
            connection_kind=None,
            connection_status='DISCONNECTED',
            firmware_error=None,
            identity_error=None,
        )

        self._enabled_ev = asyncio.Event()
        self._connected_ev = asyncio.Event()
        self._acknowledged_ev = asyncio.Event()
        self._synchronized_ev = asyncio.Event()
        self._disconnected_ev = asyncio.Event()
        self._updating_ev = asyncio.Event()

        # Initial state is disconnected
        self._disconnected_ev.set()

    def desc(self) -> StatusDescription:
        return self._status_desc

    def check_compatible(self) -> Literal[True]:
        if self._status_desc.firmware_error == 'INCOMPATIBLE':
            raise exceptions.IncompatibleFirmware()

        if self._status_desc.identity_error == 'INCOMPATIBLE':
            raise exceptions.InvalidDeviceId()

        return True

    def set_enabled(self, enabled: bool):
        self._status_desc.enabled = enabled

        if enabled:
            self._enabled_ev.set()
        else:
            self._enabled_ev.clear()

    def is_enabled(self) -> bool:
        return self._enabled_ev.is_set()

    async def wait_enabled(self):
        await self._enabled_ev.wait()

    def set_connected(self,
                      connection_kind: ConnectionKind_,
                      address: str):
        self._status_desc.address = address
        self._status_desc.connection_kind = connection_kind
        self._status_desc.connection_status = 'CONNECTED'

        LOGGER.info(f'>>> CONNECTED ({connection_kind})')
        self._connected_ev.set()
        self._acknowledged_ev.clear()
        self._synchronized_ev.clear()
        self._disconnected_ev.clear()

    def is_connected(self) -> bool:
        return self._connected_ev.is_set()

    async def wait_connected(self) -> Literal[True]:
        return await self._connected_ev.wait()

    def set_acknowledged(self, controller: ControllerDescription):
        if self._synchronized_ev.is_set():
            # Do not revert to acknowledged if we're already synchronized.
            # For there to be a meaningful change,
            # there must have been a disconnect first.
            return

        config = utils.get_config()
        service = self._status_desc.service

        wildcard_id = not service.device.device_id
        compatible_firmware = service.firmware.proto_version == controller.firmware.proto_version \
            or bool(config.skip_version_check)
        matching_firmware = service.firmware.firmware_version == controller.firmware.firmware_version
        compatible_identity = service.device.device_id == controller.device.device_id \
            or wildcard_id

        if not compatible_firmware:
            LOGGER.warning('Handshake error: incompatible firmware')

        if not compatible_identity:
            LOGGER.warning('Handshake error: incompatible device ID')

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

        self._status_desc.connection_status = 'ACKNOWLEDGED'
        self._status_desc.controller = controller
        self._status_desc.firmware_error = firmware_error
        self._status_desc.identity_error = identity_error

        LOGGER.info('>>> ACKNOWLEDGED')
        self._acknowledged_ev.set()

    def is_acknowledged(self) -> bool:
        return self._acknowledged_ev.is_set()

    async def wait_acknowledged(self) -> Literal[True]:
        return await self._acknowledged_ev.wait()

    def set_synchronized(self):
        if not self._acknowledged_ev.is_set():
            raise RuntimeError('Failed to set synchronized status: '
                               'service is not acknowledged')

        self._status_desc.connection_status = 'SYNCHRONIZED'

        LOGGER.info('>>> SYNCHRONIZED')
        self._synchronized_ev.set()

    def is_synchronized(self) -> bool:
        return self._synchronized_ev.is_set()

    async def wait_synchronized(self) -> Literal[True]:
        return await self._synchronized_ev.wait()

    def set_updating(self):
        self._status_desc.connection_status = 'UPDATING'

        LOGGER.info('>>> UPDATING')
        self._updating_ev.set()

    def is_updating(self) -> bool:
        return self._updating_ev.is_set()

    async def wait_updating(self) -> Literal[True]:
        return await self._updating_ev.wait()

    def set_disconnected(self):
        self._status_desc.controller = None
        self._status_desc.address = None
        self._status_desc.connection_kind = None
        self._status_desc.connection_status = 'DISCONNECTED'
        self._status_desc.firmware_error = None
        self._status_desc.identity_error = None

        LOGGER.info('>>> DISCONNECTED')
        self._connected_ev.clear()
        self._acknowledged_ev.clear()
        self._synchronized_ev.clear()
        self._updating_ev.clear()
        self._disconnected_ev.set()

    def is_disconnected(self) -> bool:
        return self._disconnected_ev.is_set()

    async def wait_disconnected(self) -> Literal[True]:
        return await self._disconnected_ev.wait()


def setup():
    CV.set(StateMachine())
