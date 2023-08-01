"""
Regularly suggest UTC time to the controller.
This is a backup mechanism to NTP, used if the controller has no internet access.
"""

import asyncio
from datetime import datetime

from aiohttp import web
from brewblox_service import brewblox_logger, features, repeater, strex

from brewblox_devcon_spark import const, controller, service_status
from brewblox_devcon_spark.models import Block, ServiceConfig

LOGGER = brewblox_logger(__name__)
ERROR_INTERVAL_S = 10


class TimeSync(repeater.RepeaterFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)

        config: ServiceConfig = app['config']
        self.interval_s = config.time_sync_interval
        self.enabled = self.interval_s > 0

    async def prepare(self):
        if not self.enabled:
            raise repeater.RepeaterCancelled()

    async def run(self):
        try:
            await service_status.wait_synchronized(self.app)
            await controller.fget(self.app).patch_block(Block(
                nid=const.SYSINFO_NID,
                type='SysInfo',
                data={'systemTime': datetime.now()},
            ))
            await asyncio.sleep(self.interval_s)

        except Exception as ex:
            LOGGER.debug(f'{self} exception: {strex(ex)}')
            await asyncio.sleep(ERROR_INTERVAL_S)
            raise ex


def setup(app: web.Application):
    features.add(app, TimeSync(app))


def fget(app: web.Application) -> TimeSync:
    return features.get(app, TimeSync)
