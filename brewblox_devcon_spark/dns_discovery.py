"""
mDNS discovery of Spark devices
"""

import asyncio
from socket import AF_INET, inet_ntoa

from aiozeroconf import ServiceBrowser, ServiceStateChange, Zeroconf
from brewblox_service import brewblox_logger

BREWBLOX_DNS_TYPE = '_brewblox._tcp.local.'

LOGGER = brewblox_logger(__name__)


async def _discover(loop, id: str):
    queue = asyncio.Queue()
    conf = Zeroconf(loop, address_family=[AF_INET])

    async def add_service(service_type, name):
        info = await conf.get_service_info(service_type, name)
        await queue.put(info)

    def sync_change_handler(_, service_type, name, state_change):
        if state_change is ServiceStateChange.Added:
            asyncio.ensure_future(add_service(service_type, name))

    try:
        ServiceBrowser(conf, BREWBLOX_DNS_TYPE, handlers=[sync_change_handler])
        while True:
            info = await queue.get()
            addr = inet_ntoa(info.address)
            if addr == '0.0.0.0':
                continue  # discard simulators
            if id is None or info.server == f'{id}.local.':
                LOGGER.info(f'Discovered {info.name} @ {addr}:{info.port}')
                return addr, info.port
            else:
                LOGGER.info(f'Discarding {info.name} @ {addr}:{info.port}')
    finally:
        await conf.close()


async def discover(loop, id: str, timeout: int = 0):
    if timeout:
        return await asyncio.wait_for(_discover(loop, id), timeout=timeout)
    else:
        return await _discover(loop, id)
