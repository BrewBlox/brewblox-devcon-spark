"""
REST API for Spark blocks
"""


import json

from aiohttp import web
from aiohttp_pydantic import PydanticView
from aiohttp_pydantic.oas.typing import r200, r201
from brewblox_service import brewblox_logger, mqtt

from brewblox_devcon_spark import controller
from brewblox_devcon_spark.models import (Block, BlockIdentity,
                                          BlockIdentityList, BlockList,
                                          BlockNameChange, ServiceConfig)

LOGGER = logging.getLogger(__name__)
routes = web.RouteTableDef()


def setup(app: web.Application):
    app.router.add_routes(routes)


class BlocksView(PydanticView):
    def __init__(self, request: web.Request) -> None:
        super().__init__(request)
        self.app = request.app
        self.config = utils.get_config()
        self.controller = controller.fget(self.app)

    async def publish(self, changed: list[Block] = None, deleted: list[BlockIdentity] = None):
        changed = [v.dict() for v in changed] if changed else []
        deleted = [v.id for v in deleted] if deleted else []
        name = self.config.name
        await mqtt.publish(self.app,
                           topic=f'{self.config.state_topic}/{name}/patch',
                           payload=json.dumps({
                               'key': name,
                               'type': 'Spark.patch',
                               'ttl': '1d',
                               'data': {
                                   'changed': changed,
                                   'deleted': deleted,
                               },
                           }),
                           err=False,
                           )


@routes.view('/blocks/create')
class CreateView(BlocksView):
    async def post(self, args: Block) -> r201[Block]:
        """
        Create new block.

        Tags: Blocks
        """
        block = await self.controller.create_block(args)
        await self.publish(changed=[block])
        return web.json_response(
            block.dict(),
            status=201
        )


@routes.view('/blocks/read')
class ReadView(BlocksView):
    async def post(self, args: BlockIdentity) -> r200[Block]:
        """
        Read block.

        Tags: Blocks
        """
        block = await self.controller.read_block(args)
        return web.json_response(
            block.dict()
        )


@routes.view('/blocks/read/logged')
class ReadLoggedView(BlocksView):
    async def post(self, args: BlockIdentity) -> r200[Block]:
        """
        Read block. Data only includes logged fields.

        Tags: Blocks
        """
        block = await self.controller.read_logged_block(args)
        return web.json_response(
            block.dict()
        )


@routes.view('/blocks/read/stored')
class ReadStoredView(BlocksView):
    async def post(self, args: BlockIdentity) -> r200[Block]:
        """
        Read block. Data only includes persistent fields.

        Tags: Blocks
        """
        block = await self.controller.read_stored_block(args)
        return web.json_response(
            block.dict()
        )


@routes.view('/blocks/write')
class WriteView(BlocksView):
    async def post(self, args: Block) -> r200[Block]:
        """
        Write to existing block.

        Tags: Blocks
        """
        block = await self.controller.write_block(args)
        await self.publish(changed=[block])
        return web.json_response(
            block.dict()
        )


@routes.view('/blocks/patch')
class PatchView(BlocksView):
    async def post(self, args: Block) -> r200[Block]:
        """
        Patch existing block.

        Tags: Blocks
        """
        block = await self.controller.patch_block(args)
        await self.publish(changed=[block])
        return web.json_response(
            block.dict()
        )


@routes.view('/blocks/delete')
class DeleteView(BlocksView):
    async def post(self, args: BlockIdentity) -> r200[BlockIdentity]:
        """
        Delete block.

        Tags: Blocks
        """
        ident = await self.controller.delete_block(args)
        await self.publish(deleted=[ident])
        return web.json_response(
            ident.dict()
        )


@routes.view('/blocks/batch/create')
class BatchCreateView(BlocksView):
    async def post(self, args: BlockList) -> r200[list[Block]]:
        """
        Create multiple blocks.

        Tags: Blocks
        """
        blocks_in = args.__root__
        blocks_out = []
        for block in blocks_in:
            blocks_out.append(await self.controller.create_block(block))
        await self.publish(changed=blocks_out)
        return web.json_response([
            block.dict() for block in blocks_out
        ],
            status=201)


@routes.view('/blocks/batch/read')
class BatchReadView(BlocksView):
    async def post(self, args: BlockIdentityList) -> r200[list[Block]]:
        """
        Read multiple existing blocks.

        Tags: Blocks
        """
        blocks_in = args.__root__
        blocks_out = []
        for block in blocks_in:
            blocks_out.append(await self.controller.read_block(block))
        return web.json_response([
            block.dict() for block in blocks_out
        ])


@routes.view('/blocks/batch/write')
class BatchWriteView(BlocksView):
    async def post(self, args: BlockList) -> r200[list[Block]]:
        """
        Write multiple existing blocks.

        Tags: Blocks
        """
        blocks_in = args.__root__
        blocks_out = []
        for block in blocks_in:
            blocks_out.append(await self.controller.write_block(block))
        await self.publish(changed=blocks_out)
        return web.json_response([
            block.dict() for block in blocks_out
        ])


@routes.view('/blocks/batch/patch')
class BatchPatchView(BlocksView):
    async def post(self, args: BlockList) -> r200[list[Block]]:
        """
        Patch multiple existing blocks.

        Tags: Blocks
        """
        blocks_in = args.__root__
        blocks_out = []
        for block in blocks_in:
            blocks_out.append(await self.controller.patch_block(block))
        await self.publish(changed=blocks_out)
        return web.json_response([
            block.dict() for block in blocks_out
        ])


@routes.view('/blocks/batch/delete')
class BatchDeleteView(BlocksView):
    async def post(self, args: BlockIdentityList) -> r200[list[Block]]:
        """
        Delete multiple existing blocks.

        Tags: Blocks
        """
        idents_in = args.__root__
        idents_out = []
        for ident in idents_in:
            idents_out.append(await self.controller.delete_block(ident))
        await self.publish(deleted=idents_out)
        return web.json_response([
            ident.dict() for ident in idents_out
        ])


@routes.view('/blocks/all/read')
class ReadAllView(BlocksView):
    async def post(self) -> r200[list[Block]]:
        """
        Read all blocks.

        Tags: Blocks
        """
        blocks = await self.controller.read_all_blocks()
        return web.json_response(
            [v.dict() for v in blocks]
        )


@routes.view('/blocks/all/read/logged')
class ReadAllLoggedView(BlocksView):
    async def post(self) -> r200[list[Block]]:
        """
        Read all blocks. Only includes logged fields.

        Tags: Blocks
        """
        blocks = await self.controller.read_all_logged_blocks()
        return web.json_response(
            [v.dict() for v in blocks]
        )


@routes.view('/blocks/all/read/stored')
class ReadAllStoredView(BlocksView):
    async def post(self) -> r200[list[Block]]:
        """
        Read all blocks. Only includes stored fields.

        Tags: Blocks
        """
        blocks = await self.controller.read_all_stored_blocks()
        return web.json_response(
            [v.dict() for v in blocks]
        )


@routes.view('/blocks/all/delete')
class DeleteAllView(BlocksView):
    async def post(self) -> r200[list[BlockIdentity]]:
        """
        Delete all user blocks.

        Tags: Blocks
        """
        idents = await self.controller.clear_blocks()
        await self.publish(deleted=idents)
        return web.json_response(
            [v.dict() for v in idents]
        )


@routes.view('/blocks/cleanup')
class CleanupView(BlocksView):
    async def post(self) -> r200[list[BlockIdentity]]:
        """
        Clean unused block IDs.

        Tags: Blocks
        """
        idents = await self.controller.remove_unused_ids()
        return web.json_response(
            [v.dict() for v in idents]
        )


@routes.view('/blocks/rename')
class RenameView(BlocksView):
    async def post(self, args: BlockNameChange) -> r200[BlockIdentity]:
        """
        Rename existing block.

        Tags: Blocks
        """
        ident = await self.controller.rename_block(args)
        return web.json_response(
            ident.dict()
        )


@routes.view('/blocks/discover')
class DiscoverView(BlocksView):
    async def post(self) -> r200[list[Block]]:
        """
        Discover newly connected OneWire devices.

        Tags: Blocks
        """
        blocks = await self.controller.discover_blocks()
        return web.json_response(
            [v.dict() for v in blocks]
        )


@routes.view('/blocks/validate')
class ValidateView(BlocksView):
    async def post(self, block: Block) -> r200[Block]:
        """
        Validate block data.
        This checks whether the block can be serialized.
        It will not be sent to the controller.

        Tags: Blocks
        """
        block = await self.controller.validate(block)
        return web.json_response(
            block.dict()
        )
