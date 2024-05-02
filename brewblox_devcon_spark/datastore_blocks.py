"""
Stores sid/nid relations for blocks
"""
import logging
from contextvars import ContextVar

from bidict import OnDup, OnDupAction, bidict

LOGGER = logging.getLogger(__name__)

CV: ContextVar[bidict[str, int]] = ContextVar('datastore_blocks.bidict')


def setup():
    bd = bidict()
    bd.on_dup = OnDup(key=OnDupAction.DROP_OLD,
                      val=OnDupAction.DROP_OLD)
    CV.set(bd)
