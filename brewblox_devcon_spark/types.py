from typing import Any, Optional, TypedDict


class BlockIds(TypedDict):
    id: Optional[str]
    nid: Optional[int]


class Block(TypedDict):
    id: str
    nid: Optional[int]
    serviceId: str
    groups: list[int]
    type: str
    data: dict[str, Any]


class StoreEntry(TypedDict):
    keys: tuple[str, int]
    data: dict


class Backup(TypedDict):
    blocks: list[Block]
    store: list[StoreEntry]


class BackupLoadResult(TypedDict):
    messages: list[str]
