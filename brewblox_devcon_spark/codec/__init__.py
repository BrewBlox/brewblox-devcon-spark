"""
Default exports for codec module
"""

from aiohttp import web

from . import codec, unit_conversion
from .codec import Codec, TranscodeFunc_, fget
from .opts import CodecOpts, FilterOpt, MetadataOpt, ProtoEnumOpt
from .unit_conversion import get_converter

__all__ = [
    'Codec',
    'fget',
    'get_converter',
    'setup',
    'CodecOpts',
    'ProtoEnumOpt',
    'FilterOpt',
    'MetadataOpt',

    # Types
    'TranscodeFunc_',
]


def setup(app: web.Application):
    unit_conversion.setup(app)
    codec.setup(app)
