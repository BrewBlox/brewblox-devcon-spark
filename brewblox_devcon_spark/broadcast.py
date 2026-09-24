"""
Intermittently broadcasts status and blocks to the eventbus.

The broadcaster keeps a cache of the blocks, and ticks every `broadcast_interval`.
A tick reads the blocks whose readonly state changed since the previous tick (a CHANGED read),
merges them into the cache, and publishes history for all blocks
and a patch event with the complete blocks that changed.

Some ticks read all blocks instead (a full read): the first tick of a session,
every `full_read_interval`, and every tick after the cache lost track of the controller.
Those publish the retained full state event instead of the patch.
Values that CHANGED reads do not update (`skip_changed`) are only in the history of full-read ticks.

If a tick fails, it publishes nothing, and the next tick is a full read.
If the service is not synchronized, only the status is published, every `full_read_interval`.
"""

import asyncio
import copy
import logging
from collections.abc import Generator, Mapping
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass

from . import codec, command, mqtt, spark_api, state_machine, utils
from .block_analysis import calculate_claims, calculate_relations
from .command import BlockChange
from .models import (
    Block,
    FirmwareBlock,
    HistoryEvent,
    Opcode,
    ReadMode,
    ServicePatchEvent,
    ServicePatchEventData,
    ServiceStateEvent,
    ServiceStateEventData,
)

LOGGER = logging.getLogger(__name__)


@dataclass
class CachedBlock:
    seq: int
    """The send sequence number of the request whose response last updated the block."""

    type: str

    data: dict
    """Decoded data, with numeric link ids. Never shared with anything outside the cache."""


@dataclass
class ReaderView:
    seq: int
    """The send sequence number of the latest CHANGED read that sent the block, or left it out."""

    type: str

    covered: dict
    """The covered values that CHANGED read last sent (`Codec.covered_view()`)."""


class BlockCache:
    """
    The blocks on the controller, as responses to requests show them.

    Every response that changes blocks or reads them all is applied,
    whoever sent the request (see `CboxCommander.on_block_change`).
    Responses may be handled out of order: a response never replaces what a response
    to a later request stored, and deleted blocks leave a tombstone,
    so that an older read does not bring them back.

    Where the cache can not follow a change, it needs a full (DEFAULT) read.
    A full read only satisfies that if it was sent after the change.

    A CHANGED read leaves out a block if its covered state is what a previous CHANGED read sent.
    Full reads and write responses may have replaced that state in the cache since,
    so the cache keeps what CHANGED reads sent, and merges it again for the blocks a CHANGED read leaves out.

    Responses are decoded in the units of the moment.
    Only a full read switches the cache to other units: other changes in other units need a full read.

    Block names are not cached: IDs are resolved when the blocks are published.
    """

    def __init__(self):
        self.codec = codec.CV.get()
        self.converter = codec.unit_conversion.CV.get()
        self.reset(None)

    def reset(self, session: int | None):
        """
        Forgets all blocks.
        Only responses to requests sent in `session` are applied from now on:
        with None, no responses are applied.
        """
        self.session = session
        self._entries: dict[int, CachedBlock] = {}
        self._tombstones: dict[int, int] = {}
        self._views: dict[int, ReaderView] = {}
        self._dirty: set[int] = set()
        self._need_full: int | None = -1
        self._units: str | None = None

    @property
    def entries(self) -> Mapping[int, CachedBlock]:
        """The cached blocks by nid, in the order of the latest full read. Do not modify."""
        return self._entries

    @property
    def need_full(self) -> bool:
        return self._need_full is not None

    def request_full(self, seq: int = -1):
        """
        The cache can no longer follow the controller.
        Only a full read sent after the request with sequence number `seq` will fix that.
        With the default, any full read that is applied from now on will do.
        """
        if self._need_full is None or self._need_full < seq:
            self._need_full = seq

    def take_dirty(self) -> list[int]:
        """The nids of cached blocks that changed since the previous call."""
        dirty = [nid for nid in self._entries if nid in self._dirty]
        self._dirty = set()
        return dirty

    def on_block_change(self, change: BlockChange):
        """The block listener of the commander."""
        if change.session != self.session:
            return
        try:
            self._apply(change)
        except Exception:
            self.request_full(change.seq)
            raise

    def _apply(self, change: BlockChange):
        partial = change.mode == ReadMode.CHANGED or change.opcode in [Opcode.BLOCK_WRITE, Opcode.BLOCK_CREATE]
        if partial and self.converter.temperature != self._units:
            # Decoding and notifying do not yield: the current units are those of the change.
            # What a CHANGED read sent is not kept: the units may change back before the next full read.
            self._views.clear()
            self.request_full(change.seq)
            return

        match change.opcode, change.mode:
            case Opcode.BLOCK_READ_ALL, ReadMode.CHANGED:
                if change.error:
                    # Blocks the controller sent may not have arrived, and those it did not reach are not left out
                    self._views.clear()
                    self.request_full(change.seq)
                # The controller skips the blocks it already sent in a CHANGED read.
                # Blocks that came before an error must therefore still be merged.
                self._merge(change.seq, change.blocks)
            case Opcode.BLOCK_READ_ALL, ReadMode.STORED:
                pass  # Persistent fields only
            case None, _:
                # A late response, maybe to a CHANGED read, or a controller reboot
                self._views.clear()
                self.request_full(change.seq)
            case _ if change.error:
                # A partial read-all must not remove blocks.
                # A failed write may have been applied.
                self.request_full(change.seq)
            case Opcode.BLOCK_READ_ALL, _:
                self._apply_full(change.seq, change.blocks)
            case Opcode.BLOCK_WRITE | Opcode.BLOCK_CREATE, _:
                for block in change.blocks:
                    self._replace(change.seq, block)
            case Opcode.BLOCK_DELETE, _:
                self._remove(change.seq, change.nid)
            case _:
                # CLEAR_BLOCKS or BLOCK_DISCOVER
                self.request_full(change.seq)

    def _deleted_after(self, nid: int, seq: int) -> bool:
        return self._tombstones.get(nid, -1) > seq

    def _updated(self, seq: int, block: FirmwareBlock) -> CachedBlock:
        entry = self._entries.get(block.nid)
        updated = CachedBlock(seq, block.type, copy.deepcopy(block.data))
        if entry is None or (entry.type, entry.data) != (updated.type, updated.data):
            self._dirty.add(block.nid)
        return updated

    def _apply_full(self, seq: int, blocks: list[FirmwareBlock]):
        entries: dict[int, CachedBlock] = {}
        for block in blocks:
            entry = self._entries.get(block.nid)
            if self._deleted_after(block.nid, seq):
                continue
            if entry is not None and entry.seq > seq:
                entries[block.nid] = entry
            else:
                entries[block.nid] = self._updated(seq, block)

        # Blocks absent from the read are gone, unless they were created after it
        entries.update({nid: v for nid, v in self._entries.items() if nid not in entries and v.seq > seq})
        self._entries = entries
        self._tombstones = {nid: v for nid, v in self._tombstones.items() if v > seq}
        self._views = {nid: v for nid, v in self._views.items() if nid in entries}

        if self._need_full is not None and self._need_full < seq:
            self._need_full = None

        units = self.converter.temperature
        if units != self._units:
            self._units = units
            self._views.clear()
            # Blocks kept from responses to later requests are in the old units
            if newer := [v.seq for v in entries.values() if v.seq > seq]:
                self.request_full(max(newer))

    def _merge(self, seq: int, blocks: list[FirmwareBlock]):
        sent = set()
        for block in blocks:
            sent.add(block.nid)
            if self._deleted_after(block.nid, seq):
                continue

            covered = self.codec.covered_view(block.type, block.data)
            if covered is not None:
                self._views[block.nid] = ReaderView(seq, block.type, copy.deepcopy(covered))

            entry = self._entries.get(block.nid)
            if entry is not None and entry.seq > seq:
                continue
            if entry is None or entry.type != block.type:
                LOGGER.debug(f'CHANGED read of an unknown block: {block.nid} ({block.type})')
                self.request_full(seq)
                continue
            self._merge_block(seq, block.nid, entry, copy.deepcopy(block.data))

        # The controller left out the other blocks: their covered state is what it last sent.
        # Merge that again where a full read or a write response replaced it in the cache since.
        # Views are cleared when a CHANGED read fails: it is unknown what the controller left out.
        for nid, view in self._views.items():
            entry = self._entries.get(nid)
            if nid in sent or entry is None or entry.type != view.type or not view.seq < entry.seq < seq:
                continue
            self._merge_block(seq, nid, entry, copy.deepcopy(view.covered))
            view.seq = seq

    def _merge_block(self, seq: int, nid: int, entry: CachedBlock, partial: dict):
        try:
            if self.codec.merge_changed(entry.type, entry.data, partial):
                self._dirty.add(nid)
            entry.seq = seq
        except codec.NeedFullRead as ex:
            LOGGER.debug(f'CHANGED read of {nid} can not be merged: {utils.strex(ex)}')
            self.request_full(seq)

    def _replace(self, seq: int, block: FirmwareBlock):
        entry = self._entries.get(block.nid)
        if self._deleted_after(block.nid, seq):
            return
        if entry is not None and entry.seq > seq:
            # A read sent later was applied first.
            # A CHANGED read does not include what this response stored.
            self.request_full(entry.seq)
            return
        self._entries[block.nid] = self._updated(seq, block)

    def _remove(self, seq: int, nid: int):
        entry = self._entries.get(nid)
        if entry is not None and entry.seq > seq:
            return  # Created again after this delete
        self._entries.pop(nid, None)
        self._views.pop(nid, None)
        self._tombstones[nid] = max(seq, self._tombstones.get(nid, -1))


def next_deadline(deadline: float, now: float, interval: float) -> float:
    """
    The deadline after `deadline`, one `interval` later.
    If `now` is already past it, the tick ran late: its missed deadlines are skipped.
    """
    deadline += interval
    if now > deadline:
        deadline += ((now - deadline) // interval + 1) * interval
    return deadline


class Broadcaster:
    def __init__(self):
        self.config = utils.get_config()
        self.state = state_machine.CV.get()
        self.codec = codec.CV.get()
        self.cmder = command.CV.get()
        self.api = spark_api.CV.get()
        self.mqtt_client = mqtt.CV.get()
        self.cache = BlockCache()

        self.state_topic = f'{self.config.state_topic}/{self.config.name}'
        self.patch_topic = f'{self.state_topic}/patch'
        self.history_topic = f'{self.config.history_topic}/{self.config.name}'

        self._last_full: float | None = None

    @contextmanager
    def hooked(self) -> Generator[None, None, None]:
        """Applies every response the commander handles to the cache."""
        self.cmder.on_block_change = self.cache.on_block_change
        try:
            yield
        finally:
            self.cmder.on_block_change = None

    def _full_due(self, now: float) -> bool:
        interval = self.config.broadcast_interval.total_seconds()
        full_interval = self.config.full_read_interval.total_seconds()
        return (
            self._last_full is None
            or full_interval <= interval
            # Ticks start a little after their deadline: allow half a tick of jitter
            or now - self._last_full >= full_interval - interval / 2
        )

    def _to_block(self, nid: int, block_type: str, data: dict, name: str | None = None) -> Block:
        return self.api.to_block(FirmwareBlock(id=name, nid=nid, type=block_type, data=data))

    def _publish_state(self, blocks: list[Block]):
        self.mqtt_client.publish(
            self.state_topic,
            ServiceStateEvent(
                key=self.config.name,
                data=ServiceStateEventData(
                    status=self.state.desc(),
                    blocks=blocks,
                    relations=calculate_relations(blocks),
                    claims=calculate_claims(blocks),
                ),
            ).model_dump(mode='json'),
            retain=True,
        )

    async def tick(self):
        now = asyncio.get_running_loop().time()

        if not self.state.is_synchronized() or self.state.is_updating():
            self.cache.reset(None)
            if self._full_due(now):
                self._last_full = now
                self._publish_state([])
            return

        session = self.state.session
        if self.cache.session != session:
            self.cache.reset(session)

        full = self.cache.need_full or self._full_due(now)
        mode = ReadMode.DEFAULT if full else ReadMode.CHANGED

        try:
            # The cache is updated by the commander's block listener
            blocks = await self.cmder.read_all_blocks(mode, timeout=self.config.broadcast_timeout)
        except Exception as ex:
            LOGGER.warning(f'Failed to read {mode.name} blocks: {utils.strex(ex)}')
            self.cache.request_full()
            return

        # The controller reconnected during the read, or merging it failed
        if self.state.session != session or (not full and self.cache.need_full):
            return

        if full:
            self._last_full = now

        # Only full reads include block names
        names = {block.nid: block.id for block in blocks}
        entries = self.cache.entries

        history = {}
        for nid, entry in entries.items():
            logged = self._to_block(
                nid, entry.type, self.codec.logged_view(entry.type, entry.data, full=full), names.get(nid)
            )
            history[logged.id] = logged.data

        self.mqtt_client.publish(
            self.history_topic,
            HistoryEvent(key=self.config.name, data=history).model_dump(mode='json'),
        )

        dirty = self.cache.take_dirty()

        if full:
            self._publish_state([self._to_block(nid, v.type, v.data, names.get(nid)) for nid, v in entries.items()])

        elif dirty:
            changed = [self._to_block(nid, entries[nid].type, entries[nid].data) for nid in dirty]
            self.mqtt_client.publish(
                self.patch_topic,
                ServicePatchEvent(key=self.config.name, data=ServicePatchEventData(changed=changed)).model_dump(
                    mode='json'
                ),
            )

    async def repeat(self):
        interval = self.config.broadcast_interval.total_seconds()

        if interval <= 0:
            LOGGER.warning(f'Cancelling broadcaster (interval={self.config.broadcast_interval})')
            return

        loop = asyncio.get_running_loop()
        deadline = loop.time()

        while True:
            try:
                await self.tick()
            except Exception as ex:
                LOGGER.error(utils.strex(ex), exc_info=self.config.debug)

            now = loop.time()
            deadline = next_deadline(deadline, now, interval)
            await asyncio.sleep(deadline - now)


@asynccontextmanager
async def lifespan():
    bc = Broadcaster()
    with bc.hooked():
        async with utils.task_context(bc.repeat()):
            yield
