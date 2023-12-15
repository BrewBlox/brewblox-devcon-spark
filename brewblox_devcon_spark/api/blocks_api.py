"""
REST API for Spark blocks
"""

import logging

from fastapi import APIRouter

from .. import controller, mqtt, utils
from ..models import Block, BlockIdentity, BlockNameChange

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix='/blocks', tags=['Blocks'])


async def publish(changed: list[Block] = None,
                  deleted: list[BlockIdentity] = None):
    config = utils.get_config()
    mqtt_client = mqtt.CV.get()
    changed = [v.model_dump(mode='json') for v in changed] if changed else []
    deleted = [v.id for v in deleted] if deleted else []
    mqtt_client.publish(f'{config.state_topic}/{config.name}/patch',
                        {
                            'key': config.name,
                            'type': 'Spark.patch',
                            'ttl': '1d',
                            'data': {
                                'changed': changed,
                                'deleted': deleted,
                            },
                        })


@router.post('/create', status_code=201)
async def blocks_create(args: Block) -> Block:
    """
    Create new block.
    """
    block = await controller.CV.get().create_block(args)
    publish(changed=[block])
    return block


@router.post('/read')
async def blocks_read(args: BlockIdentity) -> Block:
    """
    Read existing block.
    """
    block = await controller.CV.get().read_block(args)
    return block


@router.post('/read/logged')
async def blocks_read_logged(args: BlockIdentity) -> Block:
    """
    Read existing block. Data only includes logged fields.
    """
    block = await controller.CV.get().read_logged_block(args)
    return block


@router.post('/read/stored')
async def blocks_read_stored(args: BlockIdentity) -> Block:
    """
    Read existing block. Data only includes stored fields.
    """
    block = await controller.CV.get().read_stored_block(args)
    return block


@router.post('/write')
async def blocks_write(args: Block) -> Block:
    """
    Write existing block. This will replace all fields.
    """
    block = await controller.CV.get().write_block(args)
    publish(changed=[block])
    return block


@router.post('/patch')
async def blocks_patch(args: Block) -> Block:
    """
    Patch existing block. This will only replace provided fields.
    """
    block = await controller.CV.get().patch_block(args)
    publish(changed=[block])
    return block


@router.post('/delete')
async def blocks_delete(args: BlockIdentity) -> BlockIdentity:
    """
    Delete existing user block.
    """
    ident = await controller.CV.get().delete_block(args)
    publish(deleted=[ident])
    return ident


@router.post('/batch/create', status_code=201)
async def blocks_batch_create(args: list[Block]) -> list[Block]:
    """
    Create multiple new blocks.
    """
    ctlr = controller.CV.get()
    blocks = [await ctlr.create_block(block)
              for block in args]
    publish(changed=blocks)
    return blocks


@router.post('/batch/read')
async def blocks_batch_read(args: list[BlockIdentity]) -> list[Block]:
    """
    Read multiple existing blocks.
    """
    ctlr = controller.CV.get()
    blocks = [await ctlr.read_block(ident)
              for ident in args]
    return blocks


@router.post('/batch/write')
async def blocks_batch_write(args: list[Block]) -> list[Block]:
    """
    Write multiple existing blocks. This will replace all fields.
    """
    ctlr = controller.CV.get()
    blocks = [await ctlr.write_block(block)
              for block in args]
    publish(changed=blocks)
    return blocks


@router.post('/batch/patch')
async def blocks_batch_patch(args: list[Block]) -> list[Block]:
    """
    Write multiple existing blocks. This will only replace provided fields.
    """
    ctlr = controller.CV.get()
    blocks = [await ctlr.patch_block(block)
              for block in args]
    publish(changed=blocks)
    return blocks


@router.post('/batch/delete')
async def blocks_batch_delete(args: list[BlockIdentity]) -> list[BlockIdentity]:
    """
    Delete multiple existing user blocks.
    """
    ctlr = controller.CV.get()
    idents = [await ctlr.delete_block(ident)
              for ident in args]
    publish(deleted=idents)
    return idents


@router.post('/all/read')
async def blocks_all_read() -> list[Block]:
    """
    Read all existing blocks.
    """
    blocks = await controller.CV.get().read_all_blocks()
    return blocks


@router.post('/all/read/logged')
async def blocks_all_read_logged() -> list[Block]:
    """
    Read all existing blocks. Only includes logged fields.
    """
    blocks = await controller.CV.get().read_all_logged_blocks()
    return blocks


@router.post('/all/read/stored')
async def blocks_all_read_stored() -> list[Block]:
    """
    Read all existing blocks. Only includes stored fields.
    """
    blocks = await controller.CV.get().read_all_stored_blocks()
    return blocks


@router.post('/all/delete')
async def blocks_all_delete() -> list[BlockIdentity]:
    """
    Delete all user blocks.
    """
    idents = await controller.CV.get().clear_blocks()
    publish(deleted=idents)
    return idents


@router.post('/cleanup')
async def blocks_cleanup() -> list[BlockIdentity]:
    """
    Clean unused block IDs.
    """
    idents = await controller.CV.get().remove_unused_ids()
    return idents


@router.post('/rename')
async def blocks_rename(args: BlockNameChange) -> BlockIdentity:
    """
    Rename existing block.
    """
    config = utils.get_config()
    ctlr = controller.CV.get()
    ident = await ctlr.rename_block(args)
    block = await ctlr.read_block(ident)
    old_ident = BlockIdentity(id=args.existing,
                              serviceId=config.name)
    publish(changed=[block], deleted=[old_ident])
    return ident


@router.post('/discover')
async def blocks_discover() -> list[Block]:
    """
    Discover new automatically created blocks.
    """
    blocks = await controller.CV.get().discover_blocks()
    publish(changed=blocks)
    return blocks


@router.post('/validate')
async def blocks_validate(args: Block) -> Block:
    """
    Validate block data.
    This checks whether the block can be serialized.
    It will not be sent to the controller.
    """
    block = await controller.CV.get().validate(args)
    return block
