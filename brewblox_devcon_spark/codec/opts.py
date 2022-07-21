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
    TYPED = auto()


class ProtoEnumOpt(Enum):
    INT = auto()
    STR = auto()


class DateFormatOpt(Enum):
    MILLISECONDS = auto()
    SECONDS = auto()
    ISO8601 = auto()


@dataclass(frozen=True)
class DecodeOpts():
    filter: FilterOpt = FilterOpt.ALL
    metadata: MetadataOpt = MetadataOpt.TYPED
    enums: ProtoEnumOpt = ProtoEnumOpt.STR
    dates: DateFormatOpt = DateFormatOpt.ISO8601
