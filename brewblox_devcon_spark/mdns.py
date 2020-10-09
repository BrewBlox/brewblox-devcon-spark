"""
mDNS discovery of Spark devices
"""

import asyncio
from contextlib import suppress
from socket import AF_INET, inet_aton, inet_ntoa

from aiozeroconf import ServiceBrowser, ServiceStateChange, Zeroconf
from async_timeout import timeout
from brewblox_service import brewblox_logger

DEFAULT_TIMEOUT_S = 5
SIM_ADDR = inet_aton('0.0.0.0')

LOGGER = brewblox_logger(__name__)


async def _discover(id: str, dns_type: str, single: bool):
    queue = asyncio.Queue()
    conf = Zeroconf(asyncio.get_event_loop(), address_family=[AF_INET])

    async def add_service(service_type, name):
        info = await conf.get_service_info(service_type, name)
        await queue.put(info)

    def sync_change_handler(_, service_type, name, state_change):
        if state_change is ServiceStateChange.Added:
            asyncio.create_task(add_service(service_type, name))

    try:
        ServiceBrowser(conf, dns_type, handlers=[sync_change_handler])
        match = f'{id}.local.'.lower() if id else None

        while True:
            info = await queue.get()
            if info.address in [None, SIM_ADDR]:
                continue  # discard unknown addresses and simulators
            addr = inet_ntoa(info.address)
            if match is None or info.server.lower() == match:
                serial = info.server[:-len('.local.')]
                LOGGER.info(f'Discovered {serial} @ {addr}:{info.port}')
                yield addr, info.port, serial
                if single:
                    return
            else:
                LOGGER.info(f'Discarding {info.name} @ {addr}:{info.port}')
    finally:
        await conf.close()


async def discover_all(id: str, dns_type: str, timeout_v: float):
    with suppress(asyncio.TimeoutError):
        async with timeout(timeout_v):
            async for res in _discover(id, dns_type, False):
                yield res


async def discover_one(id: str, dns_type: str, timeout_v: float = None):
    async with timeout(timeout_v):
        retv = None
        async for res in _discover(id, dns_type, True):
            retv = res
        return retv
