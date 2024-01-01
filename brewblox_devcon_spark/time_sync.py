"""
Regularly suggest UTC time to the controller.
This is a backup mechanism to NTP, used if the controller has no internet access.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from . import const, control, state_machine, utils
from .models import Block

LOGGER = logging.getLogger(__name__)


class TimeSync:

    def __init__(self) -> None:
        self.config = utils.get_config()
        self.state = state_machine.CV.get()
        self.ctrl = control.CV.get()

    async def run(self):
        await self.state.wait_synchronized()
        now = datetime.now()
        await self.ctrl.patch_block(Block(
            nid=const.SYSINFO_NID,
            type=const.SYSINFO_BLOCK_TYPE,
            data={'systemTime': now},
        ))
        LOGGER.debug(f'Time sync: {now=}')

    async def repeat(self):
        interval = self.config.time_sync_interval
        retry_interval = self.config.time_sync_retry_interval

        if interval <= timedelta():
            LOGGER.warning(f'Cancelling time sync (interval={interval})')
            return

        while True:
            try:
                await self.run()
                await asyncio.sleep(interval.total_seconds())
            except Exception as ex:
                LOGGER.error(utils.strex(ex), exc_info=self.config.debug)
                await asyncio.sleep(retry_interval.total_seconds())


@asynccontextmanager
async def lifespan():
    sync = TimeSync()
    async with utils.task_context(sync.repeat()):
        yield
