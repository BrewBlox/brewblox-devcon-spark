"""
Store regular backups of blocks on disk
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

from aiohttp import web
from brewblox_service import brewblox_logger, features, repeater, strex

from brewblox_devcon_spark import controller, exceptions, service_status
from brewblox_devcon_spark.models import (Backup, BackupApplyResult,
                                          BackupIdentity, ServiceConfig)

LOGGER = brewblox_logger(__name__)
BASE_BACKUP_DIR = Path('./backup')


class BackupStorage(repeater.RepeaterFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)

        config: ServiceConfig = app['config']
        self.name = config['name']
        self.dir = BASE_BACKUP_DIR / self.name
        self.interval_s = config['backup_interval']
        self.retry_interval_s = config['backup_retry_interval']

        if self.retry_interval_s <= 0:
            self.retry_interval_s = self.interval_s

        self.last_ok = False
        self.enabled = self.interval_s > 0

    async def prepare(self):
        self.dir.mkdir(mode=0o777, parents=True, exist_ok=True)

        if not self.enabled:
            raise repeater.RepeaterCancelled()

    async def run(self):
        try:
            self.last_ok = False
            interval = self.interval_s if self.last_ok else self.retry_interval_s
            await asyncio.sleep(interval)

            if service_status.is_synchronized(self.app):
                name = f'autosave_blocks_{self.name}_' + datetime.today().strftime('%Y-%m-%d')
                await self.save(BackupIdentity(name=name))
                self.last_ok = True

        except Exception as ex:
            LOGGER.debug(f'{self} exception: {strex(ex)}')
            raise ex

    async def save_portable(self) -> Backup:
        return await controller.fget(self.app).make_backup()

    async def load_portable(self, data: Backup) -> BackupApplyResult:
        return await controller.fget(self.app).apply_backup(data)

    async def all(self) -> list[BackupIdentity]:
        return [BackupIdentity(name=f.stem)
                for f
                in self.dir.glob('*.json')
                if f.is_file()]

    async def read(self, ident: BackupIdentity) -> Backup:
        infile = self.dir / f'{ident.name}.json'
        LOGGER.debug(f'Reading backup from {infile.resolve()}')

        with infile.open('r') as f:
            return Backup(**json.load(f))

    async def write(self, data: Backup) -> Backup:
        if not data.name:
            raise exceptions.InvalidInput('Missing name in backup')
        outfile = self.dir / f'{data.name}.json'
        LOGGER.debug(f'Writing backup to {outfile.resolve()}')

        with outfile.open('w') as f:
            json.dump(data.dict(), f)
        return data

    async def save(self, ident: BackupIdentity):
        data = await controller.fget(self.app).make_backup()
        data.name = ident.name
        await self.write(data)
        return data

    async def load(self, ident: BackupIdentity) -> BackupApplyResult:
        data = await self.read(ident)
        return await controller.fget(self.app).apply_backup(data)


def setup(app: web.Application):
    features.add(app, BackupStorage(app))


def fget(app: web.Application) -> BackupStorage:
    return features.get(app, BackupStorage)
