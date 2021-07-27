from typing import Any, Dict, List, Optional, Tuple

from typing_extensions import TypedDict


class BlockIds(TypedDict):
    id: Optional[str]
    nid: Optional[int]


class Block(TypedDict):
    id: str
    nid: Optional[int]
    serviceId: str
    groups: List[int]
    type: str
    data: Dict[str, Any]


class StoreEntry(TypedDict):
    keys: Tuple[str, int]
    data: dict


class Backup(TypedDict):
    blocks: List[Block]
    store: List[StoreEntry]


class BackupLoadResult(TypedDict):
    messages: List[str]
