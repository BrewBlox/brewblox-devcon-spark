"""
Offers a functional interface to the device functionality
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Callable, Union

from . import (command, const, datastore_blocks, exceptions, state_machine,
               utils)
from .codec import bloxfield, sequence
from .models import (Backup, BackupApplyResult, Block, BlockIdentity,
                     BlockNameChange, FirmwareBlock, FirmwareBlockIdentity,
                     ReadMode)

LOGGER = logging.getLogger(__name__)
CV: ContextVar['SparkApi'] = ContextVar('spark_api.SparkApi')


def merge(a: dict, b: dict):
    """Merges dict b into dict a"""
    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                merge(a[key], b[key])
            else:
                a[key] = b[key]
        else:
            a[key] = b[key]
    return a


def resolve_data_ids(data: dict | list | tuple,
                     replacer: Union[Callable[[str], int],
                                     Callable[[int], str]],
                     ):
    iter = enumerate(data) \
        if isinstance(data, (list, tuple)) \
        else data.items()

    for k, v in iter:
        # Object-style link
        if bloxfield.is_link(v):
            v['id'] = replacer(v['id'])
        # Postfix-style link
        elif str(k).endswith(const.OBJECT_LINK_POSTFIX_END):
            data[k] = replacer(v)
        # Nested data - increase iteration depth
        elif isinstance(v, (dict, list, tuple)):
            resolve_data_ids(v, replacer)


class SparkApi:

    def __init__(self):
        self.config = utils.get_config()
        self.state = state_machine.CV.get()
        self.cmder = command.CV.get()
        self.block_store = datastore_blocks.CV.get()

        self._discovery_lock = asyncio.Lock()
        self._conn_check_lock = asyncio.Lock()

    def _find_nid(self, sid: str) -> int:
        if sid is None:
            return 0

        if isinstance(sid, int) or sid.isdigit():
            return int(sid)

        try:
            return self.block_store[sid]
        except KeyError:
            raise exceptions.UnknownId(f'Block ID `{sid}` not found.')

    def _find_sid(self, nid: int) -> str:
        if nid is None or nid == 0:
            return None

        if isinstance(nid, str):
            raise exceptions.DecodeException(f'Expected numeric block ID, got string `{nid}`')

        try:
            sid = self.block_store.inverse[nid]
        except KeyError:
            # If service ID not found, use numeric representation of nid
            sid = str(nid)

        return sid

    def _sync_block_id(self, block: FirmwareBlock):
        if block.id and block.nid:
            self.block_store[block.id] = block.nid

    def _sync_all_block_ids(self, blocks: list[FirmwareBlock]):
        if blocks and blocks[0].id and blocks[0].nid:
            self.block_store.clear()
            for block in blocks:
                self.block_store[block.id] = block.nid

    def _to_block_identity(self, block: FirmwareBlock) -> BlockIdentity:
        self._sync_block_id(block)

        return BlockIdentity(
            id=self._find_sid(block.nid),
            nid=block.nid,
            type=block.type,
            serviceId=self.config.name,
        )

    def _to_block(self, block: FirmwareBlock, find_sid=True) -> Block:
        if find_sid:
            self._sync_block_id(block)

        block = Block(
            **block.model_dump(),
            serviceId=self.config.name,
        )

        if find_sid and not block.id:
            block.id = self._find_sid(block.nid)

        resolve_data_ids(block.data, self._find_sid)

        # Special case, where the API data format differs from proto-ready format
        if block.type == const.SEQUENCE_BLOCK_TYPE:
            sequence.serialize(block)

        return block

    def _to_block_list(self, blocks: list[FirmwareBlock]) -> list[Block]:
        self._sync_all_block_ids(blocks)
        return [self._to_block(block) for block in blocks]

    def _to_firmware_block_identity(self, block: BlockIdentity) -> FirmwareBlockIdentity:
        sid = block.id
        nid = block.nid

        if nid is None:
            try:
                nid = self.block_store[sid]
            except KeyError:
                raise exceptions.UnknownId(f'Block ID `{sid}` not found. type={block.type}')

        return FirmwareBlockIdentity(
            id=sid,
            nid=nid,
            type=block.type,
        )

    def _to_firmware_block(self, block: Block, find_nid=True) -> FirmwareBlock:
        sid = block.id
        nid = block.nid

        if nid is None:
            try:
                nid = self.block_store[sid] if find_nid else 0
            except KeyError:
                raise exceptions.UnknownId(f'Block ID `{sid}` not found. type={block.type}')

        block = FirmwareBlock(
            id=sid,
            nid=nid,
            type=block.type,
            data=block.data,
        )

        # Special case, where the API data format differs from proto-ready format
        if block.type == const.SEQUENCE_BLOCK_TYPE:
            sequence.parse(block)

        resolve_data_ids(block.data, self._find_nid)
        return block

    async def _check_connection(self):
        """
        Sends a Noop command to controller to evaluate the connection.
        If this command also fails, prompt the commander to reconnect.

        Only do this when the service is synchronized,
        to avoid weird interactions when prompting for a handshake.
        """
        async with self._conn_check_lock:
            if self.state.is_synchronized():
                LOGGER.info('Checking connection...')
                try:
                    await self.cmder.noop()
                except Exception:
                    await self.cmder.reset_connection()

    @asynccontextmanager
    async def _execute(self, desc: str):
        """
        Generic wrapper for all controller commands.
        State-related preconditions are checked, and errors are handled.

        Args:
            desc (str):
                Human-readable function description, to be used in error messages.
        """
        if self.state.is_updating():
            raise exceptions.UpdateInProgress('Update is in progress')

        self.state.check_compatible()

        try:
            await asyncio.wait_for(
                self.state.wait_synchronized(),
                self.config.command_timeout.total_seconds())

        except asyncio.TimeoutError:
            raise exceptions.NotConnected('Timed out waiting for synchronized state')

        try:
            yield

        except exceptions.CommandTimeout as ex:
            # Wrap in a task to not delay the original response
            asyncio.create_task(self._check_connection())
            raise ex

        except Exception as ex:
            LOGGER.debug(f'Failed to execute {desc}: {utils.strex(ex)}')
            raise ex

    async def noop(self) -> None:
        """
        Send a Noop command to the controller.
        No data is written, but a welcome message is triggered as side effect.
        """
        async with self._execute('Noop'):
            await self.cmder.noop()

    async def read_block(self, block: BlockIdentity) -> Block:
        """
        Read block on controller.

        Args:
            block (BlockIdentity):
                An object containing at least a block sid or nid.
                It is valid for `block` to be a complete block,
                but all fields except the id and type will be ignored.

        Returns:
            Block:
                The desired block, as present on the controller.
        """
        async with self._execute('Read block'):
            block = self._to_firmware_block_identity(block)
            block = await self.cmder.read_block(block)
            block = self._to_block(block)
            return block

    async def read_logged_block(self, block: BlockIdentity) -> Block:
        """
        Read block on controller.
        Block data is formatted to be suitable for logging.

        Args:
            block (BlockIdentity):
                An object containing at least a block sid or nid.
                It is valid for `block` to be a complete block,
                but all fields except the id and type will be ignored.

        Returns:
            Block:
                The desired block, as present on the controller.
                Block data will only include fields explicitly
                marked for logging, and units will use the postfixed format.
        """
        async with self._execute('Read block (logged)'):
            block = self._to_firmware_block_identity(block)
            block = await self.cmder.read_block(block, ReadMode.LOGGED)
            block = self._to_block(block)
            return block

    async def read_stored_block(self, block: BlockIdentity) -> Block:
        """
        Read block on controller.
        Block data will only include persistent fields.

        Args:
            block (BlockIdentity):
                An object containing at least a block sid or nid.
                It is valid for `block` to be a complete block,
                but all fields except the id and type will be ignored.

        Returns:
            Block:
                The desired block, as present on the controller.
                Block data will only include fields that are stored
                in persistent memory on the controller.
                Non-persistent fields will be absent or set to a default value.
        """
        async with self._execute('Read block (stored)'):
            block = self._to_firmware_block_identity(block)
            block = await self.cmder.read_block(block, ReadMode.STORED)
            block = self._to_block(block)
            return block

    async def write_block(self, block: Block) -> Block:
        """
        Write to a pre-existing block on the controller.

        Args:
            block (Block):
                A complete block. Either sid or nid may be omitted,
                but all data should be present. No attempt is made
                to merge new and existing data.

        Returns:
            Block:
                The desired block, as present on the controller after writing.
        """
        async with self._execute('Write block'):
            block = self._to_firmware_block(block)
            block = await self.cmder.write_block(block)
            block = self._to_block(block)
            return block

    async def patch_block(self, block: Block) -> Block:
        """
        Write to a pre-existing block on the controller.
        Existing values will be used for all fields not present in `block.data`.

        Args:
            block (Block):
                A complete block. Either sid or nid may be omitted,
                and existing data will be used for all fields not set in block data.

        Returns:
            Block:
                The desired block, as present on the controller after writing.
        """
        async with self._execute('Patch block'):
            block = self._to_firmware_block(block)
            block = await self.cmder.patch_block(block)
            block = self._to_block(block)
            return block

    async def create_block(self, block: Block) -> Block:
        """
        Create a new block on the controller.
        sid must be set, but nid will be auto-assigned by the controller
        if not set or 0.
        The block will not be created if either sid or nid is already in use.

        Args:
            block (Block):
                A complete block.

        Returns:
            Block:
                The desired block, as present on the controller after creation.
        """
        async with self._execute('Create block'):
            block = self._to_firmware_block(block, find_nid=False)
            block = await self.cmder.create_block(block)
            block = self._to_block(block)
            return block

    async def delete_block(self, block: BlockIdentity) -> BlockIdentity:
        """
        Remove block on the controller.
        Will raise an error if the block is not present.

        Args:
            block (BlockIdentity):
                An object containing at least a block sid or nid.
                It is valid for `block` to be a complete block,
                but all fields except the id and type will be ignored.

        Returns:
            BlockIdentity:
                The actual sid, nid, and type of the removed block.
        """
        async with self._execute('Delete block'):
            block = self._to_firmware_block_identity(block)
            await self.cmder.delete_block(block)

            nid = block.nid
            sid = self.block_store.inverse[nid]
            del self.block_store[sid]
            ident = BlockIdentity(
                id=sid,
                nid=nid,
                type=block.type,
                serviceId=self.config.name,
            )
            return ident

    async def read_all_blocks(self) -> list[Block]:
        """
        Read all blocks on the controller.
        No particular order is guaranteed.

        Returns:
            list[Block]:
                All present blocks on the controller.
        """
        async with self._execute('Read all blocks'):
            blocks = await self.cmder.read_all_blocks()
            blocks = self._to_block_list(blocks)
            return blocks

    async def read_all_logged_blocks(self) -> list[Block]:
        """
        Read all blocks on the controller.
        Block data is formatted to be suitable for logging.

        Returns:
            list[Block]:
                All present blocks on the controller.
                Block data will only include fields explicitly
                marked for logging, and units will use the postfixed format.
        """
        async with self._execute('Read all blocks (logged)'):
            blocks = await self.cmder.read_all_blocks(ReadMode.LOGGED)
            blocks = self._to_block_list(blocks)
            return blocks

    async def read_all_stored_blocks(self) -> list[Block]:
        """
        Read all blocks on the controller.
        Block data is formatted to be suitable for logging.

        Returns:
            list[Block]:
                All present blocks on the controller.
                Block data will only include fields that are stored
                in persistent memory on the controller.
                Non-persistent fields will be absent or set to a default value.
        """
        async with self._execute('Read all blocks (stored)'):
            blocks = await self.cmder.read_all_blocks(ReadMode.STORED)
            blocks = self._to_block_list(blocks)
            return blocks

    async def discover_blocks(self) -> list[Block]:
        """
        Discover blocks for newly connected OneWire devices.
        The controller will create new blocks during discovery,
        and the new block will only be yielded during a single discovery.

        Returns:
            list[Block]:
                Newly discovered blocks.
        """
        async with self._execute('Discover blocks'):
            async with self._discovery_lock:
                blocks = await self.cmder.discover_blocks()
            blocks = self._to_block_list(blocks)
            return blocks

    async def clear_blocks(self) -> list[BlockIdentity]:
        """
        Remove all user-created blocks on the controller.
        System blocks will not be removed, but the display settings
        will be reset.

         Returns:
            list[BlockIdentity]:
                IDs of all removed blocks.
        """
        async with self._execute('Remove all blocks'):
            blocks = await self.cmder.clear_blocks()
            identities = [self._to_block_identity(v) for v in blocks]
            self.block_store.clear()
            await self.cmder.write_block(FirmwareBlock(
                nid=const.DISPLAY_SETTINGS_NID,
                type='DisplaySettings',
                data={},
            ))
            await self.load_block_names()
            return identities

    async def rename_block(self, change: BlockNameChange) -> BlockIdentity:
        """
        Change a block sid.

        Args:
            change (BlockNameChange):
                Existing and desired ID for the block.

        Returns:
            BlockIdentity:
                The new sid + nid.
        """
        ident = FirmwareBlockIdentity(id=change.desired,
                                      nid=self.block_store[change.existing])
        block = await self.cmder.write_block_name(ident)
        self.block_store[block.id] = block.nid
        return BlockIdentity(id=block.id,
                             nid=block.nid,
                             type=block.type,
                             serviceId=self.config.name)

    async def load_block_names(self):
        """
        Load all known block names from the controller
        """
        blocks = await self.cmder.read_all_block_names()
        self._sync_all_block_ids(blocks)

    async def make_backup(self) -> Backup:
        """
        Exports blocks and block datastore entries to a serializable format
        This only includes persistent data fields for all blocks.

        Returns:
            Backup:
                JSON-ready backup data, compatible with apply_backup().
        """
        blocks = await self.read_all_stored_blocks()
        timestamp = datetime\
            .now(tz=timezone.utc)\
            .isoformat(timespec='seconds')\
            .replace('+00:00', 'Z')
        controller_info = self.state.desc().controller

        return Backup(
            blocks=[block for block in blocks],
            store=[{'keys': [block.id, block.nid], 'data': {}}
                   for block in blocks],
            name=None,
            timestamp=timestamp,
            firmware=controller_info.firmware,
            device=controller_info.device,
        )

    async def apply_backup(self, exported: Backup) -> BackupApplyResult:
        """
        Loads backup data generated by make_backup().
        Blocks are not merged with the current controller state:
        all existing created blocks are removed before the backup is loaded.

        The loader attempts to continue on error.
        If any block could not be created, the error will be logged and suppressed.

        Args:
            exported (Backup):
                Data as exported earlier by make_backup().

        Returns:
            BackupApplyResult:
                User feedback on errors encountered during import.
        """
        async with self._discovery_lock:
            LOGGER.info('Applying backup ...')
            LOGGER.info(f'Backup timestamp = {exported.timestamp}')
            LOGGER.info(f'Backup firmware = {exported.firmware}')
            LOGGER.info(f'Backup device = {exported.device}')

            await self.clear_blocks()
            error_log = []

            # First populate the datastore, to avoid unknown links
            self.block_store.clear()
            for block in exported.blocks:
                self.block_store[block.id] = block.nid

            # Now either create or write the objects, depending on whether they are system objects
            for block in exported.blocks:
                try:
                    block = block.model_copy(deep=True)
                    if block.nid is not None and block.nid < const.USER_NID_START:
                        await self.write_block(block)
                    else:
                        # Bypass self.create_block(), to avoid meddling with store IDs
                        await self.cmder.create_block(self._to_firmware_block(block))

                except Exception as ex:
                    message = f'failed to import block. Error={utils.strex(ex)}, block={block}'
                    error_log.append(message)
                    LOGGER.error(message)

            # Sync block names with reality
            await self.load_block_names()

            return BackupApplyResult(messages=error_log)

    async def clear_wifi(self):
        """
        Clear Wifi settings on the controller.
        The controller may reboot or lose connection.
        """
        async with self._execute('Clear Wifi settings'):
            await self.cmder.clear_wifi()

    async def factory_reset(self) -> None:
        """
        Prompt the controller to perform a factory reset.
        """
        async with self._execute('Factory reset'):
            await self.cmder.factory_reset()

    async def reboot(self) -> None:
        """
        Prompt the controller to reboot itself.
        """
        async with self._execute('Reboot'):
            await self.cmder.reboot()

    async def validate(self, block: Block) -> Block:
        """
        Encode and validate the provided block.
        The block will not be written to the controller,
        and does not have to be an existing block.

        Args:
            block (Block):
                A block that at least includes type and data.
                Both sid and nid may be omitted.
        """
        async with self._execute('Validate block'):
            block = self._to_firmware_block(block, find_nid=False)
            block = await self.cmder.validate(block)
            block = self._to_block(block, find_sid=False)
            return block


def setup():
    CV.set(SparkApi())
