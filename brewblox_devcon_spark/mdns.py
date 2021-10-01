"""
mDNS discovery of Spark devices
"""

import asyncio
from collections import namedtuple
from contextlib import suppress
from socket import AF_INET, inet_aton, inet_ntoa
from typing import Generator, Optional

from aiozeroconf import ServiceBrowser, ServiceStateChange, Zeroconf
from aiozeroconf.aiozeroconf import ServiceInfo
from async_timeout import timeout
from brewblox_service import brewblox_logger

DEFAULT_TIMEOUT_S = 5
SIM_ADDR = inet_aton('0.0.0.0')
ID_KEY = 'ID'.encode()

LOGGER = brewblox_logger(__name__)

ConnectInfo = namedtuple('ConnectInfo', ['address', 'port', 'id'])


async def _discover(
    desired_id: Optional[str],
    dns_type: str,
) -> Generator[ConnectInfo, None, None]:
    queue: asyncio.Queue[ServiceInfo] = asyncio.Queue()
    conf = Zeroconf(asyncio.get_event_loop(), address_family=[AF_INET])

    async def add_service(service_type, name):
        info = await conf.get_service_info(service_type, name)
        await queue.put(info)

    def sync_change_handler(_, service_type, name, state_change):
        if state_change is ServiceStateChange.Added:
            asyncio.create_task(add_service(service_type, name))

    try:
        ServiceBrowser(conf, dns_type, handlers=[sync_change_handler])

        while True:
            info = await queue.get()
            if info.address in [None, SIM_ADDR]:
                continue  # discard unknown addresses and simulators

            addr = inet_ntoa(info.address)
            id = info.properties.get(ID_KEY, bytes()).decode().lower()

            if not id:
                LOGGER.error(f'Invalid device: {info.name} @ {addr}:{info.port} has no ID TXT property')
                continue
            elif desired_id is None or desired_id.lower() == id:
                LOGGER.info(f'Discovered {id} @ {addr}:{info.port}')
                yield ConnectInfo(addr, info.port, id)
            else:
                LOGGER.info(f'Discarding {info.name} @ {addr}:{info.port}')
    finally:
        await conf.close()


async def discover_all(
    desired_id: Optional[str],
    dns_type: str,
    timeout_v: float,
) -> Generator[ConnectInfo, None, None]:
    with suppress(asyncio.TimeoutError):
        async with timeout(timeout_v):
            async for res in _discover(desired_id, dns_type):
                yield res


async def discover_one(
    desired_id: Optional[str],
    dns_type: str,
    timeout_v: Optional[float] = None,
) -> ConnectInfo:
    async with timeout(timeout_v):
        async for res in _discover(desired_id, dns_type):
            return res
