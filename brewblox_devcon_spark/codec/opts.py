"""
Codec options
"""

from enum import Enum, auto


class DateFormatOpt(Enum):
    MILLISECONDS = auto()
    SECONDS = auto()
    ISO8601 = auto()
