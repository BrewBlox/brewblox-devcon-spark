"""
REST API for handling backups of controller data
"""


from aiohttp import web
from aiohttp_pydantic import PydanticView
from aiohttp_pydantic.oas.typing import r200
from brewblox_service import brewblox_logger

from brewblox_devcon_spark import backup_storage
from brewblox_devcon_spark.models import (Backup, BackupApplyResult,
                                          BackupIdentity)

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()


def setup(app: web.Application):
    app.router.add_routes(routes)


class BackupView(PydanticView):
    def __init__(self, request: web.Request) -> None:
        super().__init__(request)
        self.app = request.app
        self.storage = backup_storage.fget(request.app)


@routes.view('/blocks/backup/save')
class BackupSaveView(BackupView):
    async def post(self) -> r200[Backup]:
        """
        Export service blocks to a portable format.

        Tags: Backup
        """
        backup = await self.storage.save_portable()
        return web.json_response(
            backup.dict()
        )


@routes.view('/blocks/backup/load')
class BackupLoadView(BackupView):
    async def post(self, args: Backup) -> r200[BackupApplyResult]:
        """
        Import service blocks from a backup generated by /blocks/backup/save

        Tags: Backup
        """
        result = await self.storage.load_portable(args)
        return web.json_response(
            result.dict()
        )


@routes.view('/blocks/backup/stored/all')
class BackupStoredAllView(BackupView):
    async def post(self) -> r200[list[BackupIdentity]]:
        """
        List all stored backup files.

        Tags: Backup
        """
        result = await self.storage.all()
        return web.json_response(
            [v.dict() for v in result]
        )


@routes.view('/blocks/backup/stored/download')
class BackupStoredDownloadView(BackupView):
    async def post(self, args: BackupIdentity) -> r200[Backup]:
        """
        Download stored backup without applying it.

        Tags: Backup
        """
        result = await self.storage.read(args)
        return web.json_response(
            result.dict()
        )


@routes.view('/blocks/backup/stored/upload')
class BackupStoredUploadView(BackupView):
    async def post(self, args: Backup) -> r200[Backup]:
        """
        Download stored backup without applying it.

        Tags: Backup
        """
        result = await self.storage.write(args)
        return web.json_response(
            result.dict()
        )


@routes.view('/blocks/backup/stored/save')
class BackupStoredSaveView(BackupView):
    async def post(self, args: BackupIdentity) -> r200[Backup]:
        """
        Create new stored backup.

        Tags: Backup
        """
        result = await self.storage.save(args)
        return web.json_response(
            result.dict()
        )


@routes.view('/blocks/backup/stored/load')
class BackupStoredLoadView(BackupView):
    async def post(self, args: BackupIdentity) -> r200[BackupApplyResult]:
        """
        Apply stored backup.

        Tags: Backup
        """
        result = await self.storage.load(args)
        return web.json_response(
            result.dict()
        )