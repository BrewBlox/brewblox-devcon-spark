"""
Stores last known version of block data
"""

from functools import wraps
from typing import KeysView, Optional

from aiohttp import web
from brewblox_service import brewblox_logger

from brewblox_devcon_spark.models import Block, BlockIdentity
from brewblox_devcon_spark.twinkeydict import TwinKeyDict

LOGGER = brewblox_logger(__name__)

CacheT_ = TwinKeyDict[str, int, Block]


def setup(app: web.Application):
    app['block_cache'] = TwinKeyDict()


def cache_func(func):
    @wraps(func)
    def wrapped(app: web.Application, *args, **kwargs):
        cache = app['block_cache']
        return func(cache, *args, **kwargs)
    return wrapped


@cache_func
def keys(cache: CacheT_) -> KeysView[tuple[str, int]]:
    return cache.keys()


@cache_func
def get(cache: CacheT_, ident: BlockIdentity) -> Optional[Block]:
    return cache.get((ident.id, ident.nid))


@cache_func
def set(cache: CacheT_, block: Block):
    cache[block.id, block.nid] = block


@cache_func
def delete(cache: CacheT_, ident: BlockIdentity):
    if (ident.id, ident.nid) in cache:  # pragma: no cover
        del cache[ident.id, ident.nid]


@cache_func
def delete_all(cache: CacheT_):
    cache.clear()


@cache_func
def set_all(cache: CacheT_, blocks: list[Block]):
    cache.clear()
    for block in blocks:
        cache[block.id, block.nid] = block


@cache_func
def rename(cache: CacheT_, existing: str, desired: str):
    block = cache.get((existing, None))
    if block:  # pragma: no cover
        del cache[existing, None]
        block.id = desired
        cache[desired, block.nid] = block
