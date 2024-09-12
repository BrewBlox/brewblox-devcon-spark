"""
Stores sid/nid relations for blocks
"""
import logging
from contextvars import ContextVar

from bidict import OnDup, OnDupAction, bidict
from httpx import AsyncClient

from . import const, state_machine, utils
from .models import DatastoreSingleQuery, TwinKeyEntriesBox

LOGGER = logging.getLogger(__name__)

CV: ContextVar[bidict[str, int]] = ContextVar('datastore_blocks.bidict')


def get_legacy_redis_block_db_name() -> str:  # pragma: no cover
    config = utils.get_config()
    state = state_machine.CV.get()

    # Simulation services are identified by service name.
    # This prevents data conflicts when a simulation service
    # is reconfigured to start interacting with a controller.
    desc = state.desc()
    if desc.connection_kind == 'SIM':
        return f'simulator__{config.name}-blocks-db'
    elif desc.connection_kind == 'MOCK':
        return f'mock__{config.name}-blocks-db'
    else:
        return f'{desc.controller.device.device_id}-blocks-db'


async def extract_legacy_redis_block_names() -> list[tuple[str, int]]:  # pragma: no cover
    """
    Block names were historically stored in Redis.
    To migrate the stored block names to the controller we must do a one-time
    load of the old name table.
    """
    config = utils.get_config()
    client = AsyncClient(base_url=config.datastore_url)
    data: list[tuple[str, int]] = []

    try:
        query = DatastoreSingleQuery(id=get_legacy_redis_block_db_name(),
                                     namespace=const.SERVICE_NAMESPACE)
        content = query.model_dump(mode='json')
        resp = await utils.httpx_retry(lambda: client.post('/get', json=content))
        box = TwinKeyEntriesBox.model_validate_json(resp.text)
        data = [entry.keys for entry in box.value.data]
    except Exception:
        pass

    return data


async def remove_legacy_redis_block_names():  # pragma: no cover
    config = utils.get_config()
    client = AsyncClient(base_url=config.datastore_url)

    query = DatastoreSingleQuery(id=get_legacy_redis_block_db_name(),
                                 namespace=const.SERVICE_NAMESPACE)
    content = query.model_dump(mode='json')
    await client.post('/delete', json=content)


def setup():
    bd = bidict()
    bd.on_dup = OnDup(key=OnDupAction.DROP_OLD,
                      val=OnDupAction.DROP_OLD)
    CV.set(bd)
