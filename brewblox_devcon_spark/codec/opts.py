"""
Codec options
"""

from dataclasses import dataclass
from enum import Enum, auto


class FilterOpt(Enum):
    ALL = auto()
    LOGGED = auto()


class MetadataOpt(Enum):
    POSTFIX = auto()
    METACLASS = auto()


class ProtoEnumOpt(Enum):
    INT = auto()
    STR = auto()


@dataclass(frozen=True)
class CodecOpts():
    filter: FilterOpt = FilterOpt.ALL
    metadata: MetadataOpt = MetadataOpt.METACLASS
    enums: ProtoEnumOpt = ProtoEnumOpt.STR
