"""
Tests brewblox_devcon_spark.mdns
"""

import asyncio
from socket import inet_aton

import pytest
from aiozeroconf import ServiceInfo, ServiceStateChange

from brewblox_devcon_spark import connection, mdns

TESTED = mdns.__name__


class ServiceBrowserMock():

    def __init__(self, conf, service_type, handlers):
        print(conf, service_type, handlers)
        self.conf = conf
        self.service_type = service_type
        self.handlers = handlers

        for name in ['id0', 'id1', 'id2']:
            self.handlers[0](conf, service_type, name, ServiceStateChange.Added)
            self.handlers[0](conf, service_type, name, ServiceStateChange.Removed)


@pytest.fixture
def conf_mock(mocker):

    async def get_service_info(service_type, name):
        dns_type = connection.BREWBLOX_DNS_TYPE
        if name == 'id0':
            return ServiceInfo(
                service_type,
                f'{name}.{dns_type}',
                address=inet_aton('0.0.0.0')
            )
        if name == 'id1':
            return ServiceInfo(
                service_type,
                f'{name}.{dns_type}',
                server=f'{name}.local.',
                address=inet_aton('1.2.3.4'),
                port=1234
            )
        if name == 'id2':
            return ServiceInfo(
                service_type,
                f'{name}.{dns_type}',
                server=f'{name}.local.',
                address=inet_aton('4.3.2.1'),
                port=4321
            )

    async def close():
        pass

    m = mocker.patch(TESTED + '.Zeroconf')
    m.return_value.get_service_info = get_service_info
    m.return_value.close = close
    return m


@pytest.fixture
def browser_mock(mocker):
    return mocker.patch(TESTED + '.ServiceBrowser', ServiceBrowserMock)


async def test_discover_one(app, client, loop, browser_mock, conf_mock):
    dns_type = connection.BREWBLOX_DNS_TYPE
    assert await mdns.discover_one(None, dns_type) == ('1.2.3.4', 1234, 'id1')
    assert await mdns.discover_one('id2', dns_type) == ('4.3.2.1', 4321, 'id2')

    assert await mdns.discover_one(None, dns_type, 1) == ('1.2.3.4', 1234, 'id1')
    assert await mdns.discover_one('id2', dns_type, 1) == ('4.3.2.1', 4321, 'id2')

    with pytest.raises(asyncio.TimeoutError):
        await mdns.discover_one(loop, 'leprechauns', 0.1)


async def test_discover_all(app, client, loop, browser_mock, conf_mock):
    dns_type = connection.BREWBLOX_DNS_TYPE
    retv = []
    async for res in mdns.discover_all(None, dns_type, 0.01):
        retv.append(res)
    assert len(retv) == 2
