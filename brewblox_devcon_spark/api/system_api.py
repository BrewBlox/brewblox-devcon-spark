"""
Specific endpoints for using system objects
"""

import asyncio

from aiohttp import web
from aiohttp_apispec import docs, response_schema
from brewblox_service import brewblox_logger, mqtt, scheduler, strex

from brewblox_devcon_spark import (commander, device, exceptions,
                                   service_status, ymodem)
from brewblox_devcon_spark.api import schemas

TRANSFER_TIMEOUT_S = 30
STATE_TIMEOUT_S = 20
CONNECT_INTERVAL_S = 3
CONNECT_ATTEMPTS = 5

FLUSH_PERIOD_S = 3
REBOOT_WINDOW_S = 5

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()


def setup(app: web.Application):
    app.router.add_routes(routes)


async def shutdown_soon():  # pragma: no cover
    await asyncio.sleep(REBOOT_WINDOW_S)
    raise web.GracefulExit()


class FirmwareUpdater():

    def __init__(self, app: web.Application):
        self.app = app
        self.name = app['config']['name']
        self.simulation = app['config']['simulation']
        self.topic = app['config']['state_topic'] + f'/{self.name}/update'
        self.version = app['ini']['firmware_version'][:8]
        self.date = app['ini']['firmware_date']

    def _notify(self, msg: str):
        LOGGER.info(msg)
        asyncio.create_task(
            mqtt.publish(self.app,
                         self.topic,
                         {
                             'key': self.name,
                             'type': 'Spark.update',
                             'ttl': '10s',
                             'data': [msg]
                         },
                         err=False))

    async def _connect(self, address) -> ymodem.Connection:  # pragma: no cover
        for i in range(CONNECT_ATTEMPTS):
            try:
                await asyncio.sleep(CONNECT_INTERVAL_S)
                return await ymodem.connect(address)
            except ConnectionRefusedError:
                LOGGER.debug('Connection refused, retrying...')
        raise ConnectionRefusedError()

    async def flash(self) -> dict:  # pragma: no cover
        sender = ymodem.FileSender(self._notify)
        cmder = commander.get_commander(self.app)
        address = service_status.desc(self.app).device_address

        self._notify(f'Started updating {self.name}@{address} to version {self.version} ({self.date})')

        try:
            if not service_status.desc(self.app).is_connected:
                self._notify('Controller is not connected. Aborting update.')
                raise exceptions.NotConnected()

            if self.simulation:
                raise NotImplementedError('Firmware updates not available for simulation controllers')

            self._notify('Sending update command to controller')
            await cmder.start_update(FLUSH_PERIOD_S)

            self._notify('Waiting for normal connection to close')
            await asyncio.wait_for(
                service_status.wait_disconnected(self.app), STATE_TIMEOUT_S)

            self._notify(f'Connecting to {address}')
            conn = await self._connect(address)

            with conn.autoclose():
                await asyncio.wait_for(sender.transfer(conn), TRANSFER_TIMEOUT_S)

        except Exception as ex:
            self._notify(f'Failed to update firmware: {strex(ex)}')
            raise exceptions.FirmwareUpdateFailed(strex(ex))

        finally:
            self._notify('Scheduling service reboot')
            await scheduler.create(self.app, shutdown_soon())

        self._notify('Firmware updated!')
        return {'address': address, 'version': self.version}


class SystemApi():

    def __init__(self, app: web.Application):
        self.app = app

    async def reboot(self):
        async def wrapper():
            try:
                await device.get_device(self.app).reboot()
            except exceptions.CommandTimeout:
                pass
            except Exception as ex:  # pragma: no cover
                LOGGER.error(f'Unexpected error in reboot command: {strex(ex)}')
        asyncio.create_task(wrapper())
        return {}

    async def factory_reset(self):
        async def wrapper():
            try:
                await device.get_device(self.app).factory_reset()
            except exceptions.CommandTimeout:
                pass
            except Exception as ex:  # pragma: no cover
                LOGGER.error(f'Unexpected error in factory reset command: {strex(ex)}')
        asyncio.create_task(wrapper())
        return {}


@docs(
    tags=['System'],
    summary='Get service status',
)
@routes.get('/system/status')
@response_schema(schemas.StatusSchema)
async def check_status(request: web.Request) -> web.Response:
    return web.json_response(service_status.desc_dict(request.app))


@docs(
    tags=['System'],
    summary='Send an empty request to the controller',
)
@routes.post('/system/ping')
async def ping(request: web.Request) -> web.Response:
    return web.json_response(
        await device.get_device(request.app).noop()
    )


@docs(
    tags=['System'],
    summary='Reboot the controller',
)
@routes.post('/system/reboot')
async def reboot(request: web.Request) -> web.Response:
    return web.json_response(
        await SystemApi(request.app).reboot()
    )


@docs(
    tags=['System'],
    summary='Factory reset the controller',
)
@routes.post('/system/factory_reset')
async def factory_reset(request: web.Request) -> web.Response:
    return web.json_response(
        await SystemApi(request.app).factory_reset()
    )


@docs(
    tags=['System'],
    summary='Flash the controller firmware',
)
@routes.post('/system/flash')
async def flash(request: web.Request) -> web.Response:
    return web.json_response(
        await FirmwareUpdater(request.app).flash()
    )
