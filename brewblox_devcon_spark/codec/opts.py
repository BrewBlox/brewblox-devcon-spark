"""
Codec options
"""

from enum import Enum, auto


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
