"""
Tests brewblox_devcon_spark.mdns
"""

import asyncio
from socket import inet_aton

import pytest
from aiozeroconf import ServiceInfo, ServiceStateChange

from brewblox_devcon_spark import mdns

TESTED = mdns.__name__
DNS_TYPE = '_brewblox._tcp.local.'


class ServiceBrowserMock():

    def __init__(self, conf, service_type, handlers):
        print(conf, service_type, handlers)
        self.conf = conf
        self.service_type = service_type
        self.handlers = handlers

        for name in ['id0', 'id1', 'id2', 'id3']:
            self.handlers[0](conf, service_type, name, ServiceStateChange.Added)
            self.handlers[0](conf, service_type, name, ServiceStateChange.Removed)


@pytest.fixture
def conf_mock(mocker):

    async def get_service_info(service_type, name):
        if name == 'id0':
            return ServiceInfo(
                service_type,
                f'{name}.{DNS_TYPE}',
                address=inet_aton('0.0.0.0'),
                properties={b'ID': name.encode()},
            )
        if name == 'id1':
            return ServiceInfo(
                service_type,
                f'{name}.{DNS_TYPE}',
                server=f'{name}.local.',
                address=inet_aton('1.2.3.4'),
                port=1234,
                properties={b'ID': name.encode()},
            )
        if name == 'id2':
            return ServiceInfo(
                service_type,
                f'{name}.{DNS_TYPE}',
                server=f'{name}.local.',
                address=inet_aton('4.3.2.1'),
                port=4321,
                properties={b'ID': name.encode()},
            )
        if name == 'id3':
            return ServiceInfo(
                service_type,
                f'{name}.{DNS_TYPE}',
                server=f'{name}.local.',
                address=inet_aton('4.3.2.1'),
                port=4321,
                properties={},  # Will be discarded
            )

    async def close():
        pass

    m = mocker.patch(TESTED + '.Zeroconf', autospec=True)
    m.return_value.get_service_info = get_service_info
    m.return_value.close = close
    return m


@pytest.fixture
def browser_mock(mocker):
    return mocker.patch(TESTED + '.ServiceBrowser', ServiceBrowserMock)


async def test_discover_one(app, client, event_loop, browser_mock, conf_mock):
    assert await mdns.discover_one(None, DNS_TYPE) == ('1.2.3.4', 1234, 'id1')
    assert await mdns.discover_one('id2', DNS_TYPE) == ('4.3.2.1', 4321, 'id2')

    assert await mdns.discover_one(None, DNS_TYPE, 1) == ('1.2.3.4', 1234, 'id1')
    assert await mdns.discover_one('id2', DNS_TYPE, 1) == ('4.3.2.1', 4321, 'id2')

    with pytest.raises(asyncio.TimeoutError):
        await mdns.discover_one('leprechauns', DNS_TYPE, 0.1)


async def test_discover_all(app, client, event_loop, browser_mock, conf_mock):
    retv = []
    async for res in mdns.discover_all(None, DNS_TYPE, 0.01):
        retv.append(res)
    assert len(retv) == 2
