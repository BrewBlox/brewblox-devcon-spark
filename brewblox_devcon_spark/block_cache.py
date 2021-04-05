"""
Stores last known version of block data
"""

from functools import wraps
from typing import List, Optional

from aiohttp import web
from brewblox_service import brewblox_logger

from brewblox_devcon_spark.twinkeydict import TwinKeyDict

LOGGER = brewblox_logger(__name__)


def setup(app: web.Application):
    app['block_cache'] = TwinKeyDict()


def cache_func(func):
    @wraps(func)
    def wrapped(app: web.Application, *args, **kwargs):
        cache = app['block_cache']
        return func(cache, *args, **kwargs)
    return wrapped


@cache_func
def keys(cache: TwinKeyDict) -> List[dict]:
    return cache.keys()


@cache_func
def get(cache: TwinKeyDict, ids: dict) -> Optional[dict]:
    return cache.get((ids.get('id'), ids.get('nid')))


@cache_func
def set(cache: TwinKeyDict, block: dict) -> None:
    cache[block['id'], block['nid']] = block


@cache_func
def delete(cache: TwinKeyDict, ids: dict):
    (id, nid) = (ids.get('id'), ids.get('nid'))
    if (id, nid) in cache:  # pragma: no cover
        del cache[id, nid]


@cache_func
def delete_all(cache: TwinKeyDict):
    cache.clear()


@cache_func
def set_all(cache: TwinKeyDict, blocks: List[dict]):
    cache.clear()
    for block in blocks:
        cache[block['id'], block['nid']] = block


@cache_func
def rename(cache: TwinKeyDict, existing: str, desired: str):
    block = cache.get((existing, None))
    if block:  # pragma: no cover
        del cache[existing, None]
        block['id'] = desired
        cache[desired, block['nid']] = block
