"""
Store regular backups of blocks on disk
"""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path

from . import controller, exceptions, service_status, utils
from .models import Backup, BackupApplyResult, BackupIdentity

BASE_BACKUP_DIR = Path('./backup')
LOGGER = logging.getLogger(__name__)
CV: ContextVar['BackupStorage'] = ContextVar('backup_storage.BackupStorage')


class BackupStorage:

    def __init__(self):
        config = utils.get_config()
        self.name = config.name
        self.dir = BASE_BACKUP_DIR / self.name
        self.dir.mkdir(mode=0o777, parents=True, exist_ok=True)

        self.status = service_status.CV.get()
        self.ctlr = controller.CV.get()

    async def run(self):
        if self.status.is_synchronized():
            name = f'autosave_blocks_{self.name}_' + datetime.today().strftime('%Y-%m-%d')
            await self.save(BackupIdentity(name=name))

    async def repeat(self):
        config = utils.get_config()

        normal_interval = config.backup_interval
        retry_interval = config.backup_retry_interval

        if normal_interval.total_seconds() <= 0:
            LOGGER.info('Backup storage is disabled')
            return

        if retry_interval.total_seconds() <= 0:
            retry_interval = normal_interval

        last_ok = False
        while True:
            interval = normal_interval if last_ok else retry_interval
            await asyncio.sleep(interval.total_seconds())
            try:
                await self.run()
                last_ok = True
            except Exception as ex:
                last_ok = False
                LOGGER.error(ex, exc_info=config.debug)

    async def save_portable(self) -> Backup:
        return await self.ctlr.make_backup()

    async def load_portable(self, data: Backup) -> BackupApplyResult:
        return await self.ctlr.apply_backup(data)

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
        data = await self.ctlr.make_backup()
        data.name = ident.name
        await self.write(data)
        return data

    async def load(self, ident: BackupIdentity) -> BackupApplyResult:
        data = await self.read(ident)
        return await self.ctlr.apply_backup(data)


@asynccontextmanager
async def lifespan():
    storage = CV.get()
    task = asyncio.create_task(storage.repeat())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


def setup():
    CV.set(BackupStorage())
