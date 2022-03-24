"""
Specific endpoints for using system objects
"""

import asyncio

from aiohttp import web
from aiohttp_pydantic import PydanticView
from aiohttp_pydantic.oas.typing import r200
from brewblox_service import brewblox_logger, http, mqtt, scheduler, strex
from pydantic import BaseModel

from brewblox_devcon_spark import (commander, connection, controller,
                                   exceptions, service_status, ymodem)
from brewblox_devcon_spark.models import StatusDescription

TRANSFER_TIMEOUT_S = 30
STATE_TIMEOUT_S = 20
CONNECT_INTERVAL_S = 3
CONNECT_ATTEMPTS = 5

FLUSH_PERIOD_S = 3
SHUTDOWN_DELAY_S = 1
UPDATE_SHUTDOWN_DELAY_S = 5

ESP_URL_FMT = 'https://brewblox.blob.core.windows.net/firmware/{firmware_date}-{firmware_version}/brewblox-esp32.bin'

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()


class FlashResponse(BaseModel):
    address: str
    version: str


def setup(app: web.Application):
    app.router.add_routes(routes)


async def shutdown_soon(app: web.Application, wait: float):  # pragma: no cover
    async def delayed_shutdown():
        await asyncio.sleep(wait)
        raise web.GracefulExit()
    await scheduler.create(app, delayed_shutdown())


@routes.view('/system/status')
class StatusView(PydanticView):
    async def get(self) -> r200[StatusDescription]:
        """
        Get service status

        Tags: System
        """
        desc = service_status.desc(self.request.app)
        return web.json_response(
            desc.dict()
        )


@routes.view('/system/ping')
class PingView(PydanticView):
    async def get(self):
        """
        Ping the controller.

        Tags: System
        """
        await controller.fget(self.request.app).noop()
        return web.Response()

    async def post(self):
        """
        Ping the controller.

        Tags: System
        """
        await controller.fget(self.request.app).noop()
        return web.Response()


@routes.view('/system/reboot/controller')
class RebootControllerView(PydanticView):
    async def post(self):
        """
        Reboot the controller.

        Tags: System
        """
        await controller.fget(self.request.app).reboot()
        return web.Response()


@routes.view('/system/reboot/service')
class RebootServiceView(PydanticView):
    async def post(self):
        """
        Reboot the service.

        Tags: System
        """
        await shutdown_soon(self.request.app, SHUTDOWN_DELAY_S)
        return web.Response()


@routes.view('/system/clear_wifi')
class ClearWifiView(PydanticView):
    async def post(self):
        """
        Clear Wifi settings on the controller.
        The controller may reboot or lose connection.

        Tags: System
        """
        await controller.fget(self.request.app).clear_wifi()
        return web.Response()


@routes.view('/system/factory_reset')
class FactoryResetView(PydanticView):
    async def post(self):
        """
        Factory reset the controller.

        Tags: System
        """
        await controller.fget(self.request.app).factory_reset()
        return web.Response()


@routes.view('/system/flash')
class FlashView(PydanticView):
    def __init__(self, request: web.Request) -> None:
        super().__init__(request)
        self.app = request.app
        self.name: str = self.app['config']['name']
        self.simulation: bool = self.app['config']['simulation']
        self.topic: str = self.app['config']['state_topic'] + f'/{self.name}/update'
        self.version: str = self.app['ini']['firmware_version'][:8]
        self.date: str = self.app['ini']['firmware_date']

    def _notify(self, msg: str):
        LOGGER.info(msg)
        asyncio.create_task(
            mqtt.publish(self.app,
                         self.topic,
                         {
                             'key': self.name,
                             'type': 'Spark.update',
                             'data': {
                                 'log': [msg],
                             },
                         },
                         err=False))

    async def post(self) -> r200[FlashResponse]:  # pragma: no cover
        """
        Flash the controller firmware.

        Tags: System
        """
        ota = ymodem.OtaClient(self._notify)
        cmder = commander.fget(self.app)
        status_desc = service_status.desc(self.app)
        address = status_desc.device_address
        platform = status_desc.device_info.platform

        self._notify(f'Started updating {self.name}@{address} to version {self.version} ({self.date})')

        try:
            if not status_desc.is_connected:
                self._notify('Controller is not connected. Aborting update.')
                raise exceptions.NotConnected()

            if self.simulation:
                raise NotImplementedError('Firmware updates not available for simulation controllers')

            self._notify('Preparing update')
            service_status.set_updating(self.app)
            await asyncio.sleep(FLUSH_PERIOD_S)  # Wait for in-progress commands to finish

            self._notify('Sending update command to controller')
            await cmder.firmware_update()

            self._notify('Waiting for normal connection to close')
            await connection.fget(self.app).end()
            await asyncio.wait_for(
                service_status.wait_disconnected(self.app), STATE_TIMEOUT_S)

            if platform == 'esp32':  # pragma: no cover
                # ESP connections will always be a TCP address
                host, _ = address.split(':')
                self._notify(f'Sending update prompt to {host}')
                self._notify('The Spark will now download and apply the new firmware')
                self._notify('The update is done when the service reconnects')
                fw_url = ESP_URL_FMT.format(**self.app['ini'])
                await http.session(self.app).post(f'http://{host}:80/firmware_update', data=fw_url)

            else:
                self._notify(f'Connecting to {address}')
                conn = await ymodem.connect(address)

                with conn.autoclose():
                    await asyncio.wait_for(
                        ota.send(conn, f'firmware/brewblox-{platform}.bin'),
                        TRANSFER_TIMEOUT_S)
                    self._notify('Update done!')

        except Exception as ex:
            self._notify(f'Failed to update firmware: {strex(ex)}')
            raise exceptions.FirmwareUpdateFailed(strex(ex))

        finally:
            self._notify('Restarting service...')
            await shutdown_soon(self.app, UPDATE_SHUTDOWN_DELAY_S)

        response = FlashResponse(address=address, version=self.version)
        return web.json_response(
            response.dict()
        )
