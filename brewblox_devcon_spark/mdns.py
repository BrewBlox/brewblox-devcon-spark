"""
mDNS discovery of Spark devices
"""

import asyncio
import logging
from collections import namedtuple
from contextlib import suppress
from datetime import timedelta
from socket import AF_INET, inet_aton, inet_ntoa
from typing import AsyncGenerator

from aiozeroconf import ServiceBrowser, ServiceStateChange, Zeroconf
from aiozeroconf.aiozeroconf import ServiceInfo

SIM_ADDR = inet_aton('0.0.0.0')

LOGGER = logging.getLogger(__name__)

ConnectInfo = namedtuple('ConnectInfo', ['address', 'port', 'id'])


async def _discover(
    desired_id: str | None,
    dns_type: str,
) -> AsyncGenerator[ConnectInfo, None]:
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
            id = info.properties.get(b'ID', b'').decode().lower()

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
    desired_id: str | None,
    dns_type: str,
    timeout: timedelta,
) -> AsyncGenerator[ConnectInfo, None]:
    with suppress(asyncio.TimeoutError):
        async with asyncio.timeout(timeout.total_seconds()):
            async for res in _discover(desired_id, dns_type):  # pragma: no branch
                yield res


async def discover_one(
    desired_id: str | None,
    dns_type: str,
    timeout: timedelta,
) -> ConnectInfo:
    async with asyncio.timeout(timeout.total_seconds()):
        async for res in _discover(desired_id, dns_type):  # pragma: no branch
            return res
