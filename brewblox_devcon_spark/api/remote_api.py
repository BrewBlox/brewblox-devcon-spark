"""
Allows synchronizing controller blocks between controllers.

One service will function as master, and publish periodic updates on the eventbus.
The other service(s) will act as slaves: whenever they receive an update event,
they write the object data to the controller.
"""


import asyncio
import glob
import warnings
from concurrent.futures import CancelledError
from contextlib import suppress
from functools import partial

import dpath
from aiohttp import web
from brewblox_service import brewblox_logger, events, scheduler, strex

from brewblox_devcon_spark import device, status
from brewblox_devcon_spark.api import utils
from brewblox_devcon_spark.device import OBJECT_DATA_KEY, OBJECT_SID_KEY

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()


def setup(app: web.Application):
    app.router.add_routes(routes)


async def _receive(app: web.Application,
                   sid: str,
                   translations: dict,
                   subscription: events.EventSubscription,
                   routing: str,
                   incoming: dict
                   ):
    ctrl = device.get_controller(app)
    obj = await ctrl.read_object({OBJECT_SID_KEY: sid})
    existing = obj[OBJECT_DATA_KEY]

    LOGGER.debug(f'existing={existing}\nincoming={incoming}')

    if translations:
        for remote_path, local_path in translations.items():
            with suppress(KeyError):
                val = dpath.util.get(incoming, glob.escape(remote_path))
                dpath.util.new(existing, local_path, val)
    else:
        # No translations -> use the remote object in its entirety
        obj[OBJECT_DATA_KEY] = incoming

    await ctrl.write_object(obj)


async def _broadcast(app: web.Application,
                     sid: str,
                     exchange: str,
                     routing: str,
                     interval: int
                     ):
    publisher = events.get_publisher(app)
    spark_status = status.get_status(app)
    ctrl = device.get_controller(app)
    last_broadcast_ok = True

    while True:
        try:
            await spark_status.connected.wait()
            await asyncio.sleep(interval)
            obj = await ctrl.read_object({OBJECT_SID_KEY: sid})

            await publisher.publish(
                exchange=exchange,
                routing=routing,
                message=obj[OBJECT_DATA_KEY]
            )

            if not last_broadcast_ok:
                LOGGER.info(f'Remote publisher [{routing}] resumed Ok')
                last_broadcast_ok = True

        except CancelledError:
            break

        except Exception as ex:
            if last_broadcast_ok:
                warnings.warn(f'Remote publisher [{routing}] encountered an error: {strex(ex)}')
                last_broadcast_ok = False


class RemoteApi():

    def __init__(self, app: web.Application):
        self.app = app

    async def add_slave(self, sid: str, key: str, translations: dict):
        events.get_listener(self.app).subscribe(
            exchange_name=self.app['config']['sync_exchange'],
            routing=key,
            on_message=partial(_receive, self.app, sid, translations)
        )
        LOGGER.info(f'Added remote subscription. key = {key}, local object = {sid}')

    async def add_master(self, sid: str, interval: int):
        key = '.'.join([
            self.app['config']['name'],
            sid
        ])
        await scheduler.create_task(self.app,
                                    _broadcast(self.app,
                                               sid,
                                               self.app['config']['sync_exchange'],
                                               key,
                                               interval
                                               ))
        LOGGER.info(f'Added remote publisher. key = {key}, local object = {sid}')
        return {'key': key}


@routes.post('/remote/slave')
async def slave_create(request: web.Request) -> web.Response:
    """
    ---
    summary: Create a slave remote
    tags:
    - Spark
    - Remote
    operationId: controller.spark.remote.slave
    produces:
    - application/json
    parameters:
    -
        in: body
        name: body
        description: subscription
        required: true
        schema:
            type: object
            properties:
                id:
                    type: string
                    example: local_sensor_1
                key:
                    type: string
                    example: remote_sensor_couple_1
                translations:
                    type: object
                    example: {
                            "value": "targetvalue",
                            "nested/value": "nested/target/value"
                        }
    """
    request_args = await request.json()
    with utils.collecting_input():
        args = (
            request_args['id'],
            request_args['key'],
            request_args['translations'],
        )
    return web.json_response(
        await RemoteApi(request.app).add_slave(*args)
    )


@routes.post('/remote/master')
async def master_create(request: web.Request) -> web.Response:
    """
    ---
    summary: Create a master remote
    tags:
    - Spark
    - Remote
    operationId: controller.spark.remote.master
    produces:
    - application/json
    parameters:
    -
        in: body
        name: body
        description: subscription
        required: true
        schema:
            type: object
            properties:
                id:
                    type: string
                    example: local_sensor_1
                interval:
                    type: int
                    example: 5
    """
    request_args = await request.json()
    with utils.collecting_input():
        args = (
            request_args['id'],
            request_args['interval'],
        )
    return web.json_response(
        await RemoteApi(request.app).add_master(*args)
    )
