"""
Specific endpoints for using system objects
"""

import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks
from httpx import AsyncClient

from .. import (commander, controller, exceptions, mqtt, state_machine, utils,
                ymodem)
from ..models import (FirmwareFlashResponse, PingResponse,
                      ServiceStatusDescription)

ESP_URL_FMT = 'http://brewblox.blob.core.windows.net/firmware/{date}-{version}/brewblox-esp32.bin'

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix='/system', tags=['System'])


@router.get('/status')
async def system_status() -> ServiceStatusDescription:
    """
    Get service status.
    """
    desc = state_machine.CV.get().desc()
    return desc


@router.get('/ping')
async def system_ping_get() -> PingResponse:
    """
    Ping the controller.
    """
    await controller.CV.get().noop()
    return PingResponse()


@router.post('/ping')
async def system_ping_post() -> PingResponse:
    """
    Ping the controller.
    """
    await controller.CV.get().noop()
    return PingResponse()


@router.post('/reboot/controller')
async def system_reboot_controller():
    """
    Reboot the controller.
    """
    await controller.CV.get().reboot()
    return {}


@router.post('/reboot/service')
async def system_reboot_service(background_tasks: BackgroundTasks):
    """
    Reboot the service.
    """
    background_tasks.add_task(utils.graceful_shutdown, 'System API request')
    return {}


@router.post('/clear_wifi')
async def system_clear_wifi():
    """
    Clear Wifi settings on the controller.
    The controller may reboot or lose connection.
    """
    await controller.CV.get().clear_wifi()
    return {}


@router.post('/factory_reset')
async def system_factory_reset():
    """
    Factory reset the controller.
    This does not include firmware.
    """
    await controller.CV.get().factory_reset()
    return {}


class Flasher:

    def __init__(self) -> None:
        self.config = utils.get_config()
        self.fw_config = utils.get_fw_config()

        self.state = state_machine.CV.get()
        self.mqtt_client = mqtt.CV.get()
        self.commander = commander.CV.get()
        self.client = AsyncClient()

        self.topic = f'{self.config.state_topic}/{self.config.name}/update'
        self.fw_version = self.fw_config.firmware_version
        self.fw_date = self.fw_config.firmware_date
        self.fw_url = ESP_URL_FMT.format(date=self.fw_date,
                                         version=self.fw_version)

    def _notify(self, msg: str):
        LOGGER.info(msg)
        self.mqtt_client.publish(self.topic,
                                 {
                                     'key': self.config.name,
                                     'type': 'Spark.update',
                                     'data': {
                                         'log': [msg],
                                     },
                                 })

    async def run(self) -> FirmwareFlashResponse:
        desc = self.state.desc()
        device_id = desc.controller.device.device_id
        platform = desc.controller.platform
        connection_kind = desc.connection_kind
        address = desc.address

        if desc.connection_status not in ['ACKNOWLEDGED', 'SYNCHRONIZED']:
            self._notify('Controller is not connected. Aborting update.')
            raise exceptions.NotConnected()

        if connection_kind in ['MOCK', 'SIM']:
            self._notify('Firmware updates not available for simulation controllers.')
            raise exceptions.IncompatibleFirmware()

        try:
            self._notify(f'Started updating {device_id}@{address} to version {self.fw_version} ({self.fw_date})')

            self._notify('Preparing update')
            self.state.set_updating()
            await self.commander.wait_empty()  # Controller will send no new requests

            self._notify('Sending update command to controller')
            await self.commander.firmware_update()

            self._notify('Waiting for normal connection to close')
            await asyncio.wait_for(
                self.commander.end_connection(),
                self.config.flash_disconnect_timeout.total_seconds())

            if platform == 'esp32':  # pragma: no cover
                if connection_kind == 'TCP':
                    host, _ = address.split(':')
                    self._notify(f'Sending update prompt to {host}')
                    self._notify('The Spark will now download and apply the new firmware')
                    self._notify('The update is done when the service reconnects')
                    await self.client.post(f'http://{host}:80/firmware_update', content=self.fw_url)

                if connection_kind == 'MQTT':
                    topic = f'brewcast/cbox/fw/{address}'
                    self._notify(f'Sending update prompt to {topic}')
                    self._notify('The Spark will now download and apply the new firmware')
                    self._notify('The update is done when the service reconnects')
                    self.mqtt_client.publish(topic, self.fw_url)

            if platform in ['photon', 'p1']:
                self._notify(f'Connecting to {address}')
                conn = await ymodem.connect(address)
                ota_client = ymodem.OtaClient(self._notify)

                with conn.autoclose():
                    await asyncio.wait_for(
                        ota_client.send(conn, f'firmware/brewblox-{platform}.bin'),
                        self.config.flash_ymodem_timeout.total_seconds())
                    self._notify('Update done!')

        except Exception as ex:
            self._notify(f'Failed to update firmware: {utils.strex(ex)}')
            raise exceptions.FirmwareUpdateFailed(utils.strex(ex))

        finally:
            self._notify('Restarting service...')

        response = FirmwareFlashResponse(address=address, version=self.fw_version)
        return response


@router.post('/flash')
async def system_flash(background_tasks: BackgroundTasks) -> FirmwareFlashResponse:
    background_tasks.add_task(utils.graceful_shutdown, 'Firmware flash')
    flasher = Flasher()
    response = await flasher.run()
    return response
