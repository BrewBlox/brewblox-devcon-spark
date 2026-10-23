"""
mDNS discovery of Spark devices
"""

import asyncio
import logging
from collections import namedtuple
from collections.abc import AsyncGenerator
from contextlib import aclosing, suppress
from datetime import timedelta

from zeroconf import DNSQuestionType, IPVersion, ServiceStateChange, Zeroconf
from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo, AsyncZeroconf

# Simulators announce this address
SIM_ADDR = '0.0.0.0'

# How long to wait for the details of an announced service
INFO_TIMEOUT_MS = 3000

# Ask for multicast answers. By default, the first query asks for unicast answers,
# which some Sparks answer only when the query is repeated a second later.
QUESTION_TYPE = DNSQuestionType.QM

LOGGER = logging.getLogger(__name__)

ConnectInfo = namedtuple('ConnectInfo', ['address', 'port', 'id'])


async def _discover(
    desired_id: str | None,
    dns_type: str,
) -> AsyncGenerator[ConnectInfo, None]:
    names: asyncio.Queue[str] = asyncio.Queue()
    aiozc = AsyncZeroconf(ip_version=IPVersion.V4Only)

    def on_change(zeroconf: Zeroconf, service_type: str, name: str, state_change: ServiceStateChange):
        if state_change is ServiceStateChange.Added:
            names.put_nowait(name)

    browser = AsyncServiceBrowser(aiozc.zeroconf, dns_type, handlers=[on_change], question_type=QUESTION_TYPE)

    try:
        while True:
            name = await names.get()
            info = AsyncServiceInfo(dns_type, name)
            if not await info.async_request(aiozc.zeroconf, INFO_TIMEOUT_MS, question_type=QUESTION_TYPE):
                continue  # the service did not answer

            addresses = [a for a in info.parsed_addresses(IPVersion.V4Only) if a != SIM_ADDR]
            if not addresses:
                continue  # discard unknown addresses and simulators

            addr = addresses[0]
            id = (info.properties.get(b'ID') or b'').decode().lower()

            if not id:
                LOGGER.error(f'Invalid device: {info.name} @ {addr}:{info.port} has no ID TXT property')
                continue
            elif desired_id is None or desired_id.lower() == id:
                LOGGER.info(f'Discovered {id} @ {addr}:{info.port}')
                yield ConnectInfo(addr, info.port, id)
            else:
                LOGGER.info(f'Discarding {info.name} @ {addr}:{info.port}')
    finally:
        await browser.async_cancel()
        await aiozc.async_close()


async def discover_all(
    desired_id: str | None,
    dns_type: str,
    timeout: timedelta,
) -> AsyncGenerator[ConnectInfo, None]:
    async with aclosing(_discover(desired_id, dns_type)) as results:
        with suppress(asyncio.TimeoutError):
            async with asyncio.timeout(timeout.total_seconds()):
                async for res in results:  # pragma: no branch
                    yield res


async def discover_one(
    desired_id: str | None,
    dns_type: str,
    timeout: timedelta,
) -> ConnectInfo:
    # Closing the generator stops the browser now, not when it is garbage collected
    async with aclosing(_discover(desired_id, dns_type)) as results:
        async with asyncio.timeout(timeout.total_seconds()):
            async for res in results:  # pragma: no branch
                return res
