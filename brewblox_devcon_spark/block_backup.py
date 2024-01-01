"""
Store regular backups of blocks locally
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta

from . import control, exceptions, state_machine, utils
from .models import Backup, BackupApplyResult, BackupIdentity

LOGGER = logging.getLogger(__name__)
CV: ContextVar['BackupStorage'] = ContextVar('block_backup.BackupStorage')


class BackupStorage:

    def __init__(self):
        self.config = utils.get_config()
        self.state = state_machine.CV.get()
        self.ctrl = control.CV.get()

        self.dir = self.config.backup_root_dir / self.config.name
        self.dir.mkdir(mode=0o777, parents=True, exist_ok=True)

    async def save_portable(self) -> Backup:
        return await self.ctrl.make_backup()

    async def load_portable(self, data: Backup) -> BackupApplyResult:
        return await self.ctrl.apply_backup(data)

    async def all(self) -> list[BackupIdentity]:
        return [BackupIdentity(name=f.stem)
                for f
                in self.dir.glob('*.json')
                if f.is_file()]

    async def read(self, ident: BackupIdentity) -> Backup:
        infile = self.dir / f'{ident.name}.json'
        LOGGER.debug(f'Reading backup from {infile.resolve()}')

        with infile.open('r') as f:
            return Backup.model_validate_json(f.read())

    async def write(self, data: Backup) -> Backup:
        if not data.name:
            raise exceptions.InvalidInput('Missing name in backup')
        outfile = self.dir / f'{data.name}.json'
        LOGGER.debug(f'Writing backup to {outfile.resolve()}')

        with outfile.open('w') as f:
            f.write(data.model_dump_json())
        return data

    async def save(self, ident: BackupIdentity):
        data = await self.ctrl.make_backup()
        data.name = ident.name
        await self.write(data)
        return data

    async def load(self, ident: BackupIdentity) -> BackupApplyResult:
        data = await self.read(ident)
        return await self.ctrl.apply_backup(data)

    async def run(self):
        if self.state.is_synchronized():
            dt = datetime.today().strftime('%Y-%m-%d')
            await self.save(BackupIdentity(name=f'autosave_blocks_{self.config.name}_{dt}'))

    async def repeat(self):
        normal_interval = self.config.backup_interval
        retry_interval = self.config.backup_retry_interval
        interval = normal_interval

        if normal_interval < timedelta():
            LOGGER.warning(f'Cancelling block backups (interval={normal_interval})')
            return

        while True:
            try:
                await asyncio.sleep(interval.total_seconds())
                await self.run()
                interval = normal_interval
            except Exception as ex:
                LOGGER.error(utils.strex(ex), exc_info=self.config.debug)
                interval = retry_interval


@asynccontextmanager
async def lifespan():
    storage = CV.get()
    async with utils.task_context(storage.repeat()):
        yield


def setup():
    CV.set(BackupStorage())
