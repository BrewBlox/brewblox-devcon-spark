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


async def extract_legacy_redis_block_names() -> list[tuple[str, int]]:  # pragma: no cover
    """
    Block names were historically stored in Redis.
    To migrate the stored block names to the controller we must do a one-time
    load of the old name table.
    The Redis naming table is removed after reading to prevent repeated migrations.
    """
    config = utils.get_config()
    state = state_machine.CV.get()
    client = AsyncClient(base_url=config.datastore_url)

    # Simulation services are identified by service name.
    # This prevents data conflicts when a simulation service
    # is reconfigured to start interacting with a controller.
    desc = state.desc()
    if desc.connection_kind == 'SIM':
        device_name = f'simulator__{config.name}'
    elif desc.connection_kind == 'MOCK':
        device_name = f'mock__{config.name}'
    else:
        device_name = desc.controller.device.device_id

    data: list[tuple[str, int]] = []

    try:
        query = DatastoreSingleQuery(id=f'{device_name}-blocks-db',
                                     namespace=const.SERVICE_NAMESPACE)
        content = query.model_dump(mode='json')
        resp = await utils.httpx_retry(lambda: client.post('/get', json=content))
        box = TwinKeyEntriesBox.model_validate_json(resp.text)
        data = [entry.keys for entry in box.value.data]
        await client.post('/delete', json=content)
    except Exception:
        pass

    return data


def setup():
    bd = bidict()
    bd.on_dup = OnDup(key=OnDupAction.DROP_OLD,
                      val=OnDupAction.DROP_OLD)
    CV.set(bd)
