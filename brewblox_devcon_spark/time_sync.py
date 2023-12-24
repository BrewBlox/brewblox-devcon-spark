"""
Regularly suggest UTC time to the controller.
This is a backup mechanism to NTP, used if the controller has no internet access.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from . import const, controller, state_machine, utils
from .models import Block

ERROR_INTERVAL = timedelta(seconds=10)

LOGGER = logging.getLogger(__name__)


class TimeSync:

    async def run(self):
        await state_machine.CV.get().wait_synchronized()
        await controller.CV.get().patch_block(Block(
            nid=const.SYSINFO_NID,
            type=const.SYSINFO_BLOCK_TYPE,
            data={'systemTime': datetime.now()},
        ))

    async def repeat(self):
        config = utils.get_config()
        interval = config.time_sync_interval

        if interval <= timedelta():
            LOGGER.warn('Time sync disabled')
            return

        while True:
            try:
                await self.run()
                LOGGER.debug('Time synched')
                await asyncio.sleep(interval.total_seconds())
            except Exception as ex:
                LOGGER.error(utils.strex(ex), exc_info=config.debug)
                await asyncio.sleep(ERROR_INTERVAL.total_seconds())


@asynccontextmanager
async def lifespan():
    sync = TimeSync()
    async with utils.task_context(sync.repeat()):
        yield
