import asyncio
from datetime import timedelta
from socket import inet_aton
from unittest.mock import Mock

import pytest
from aiozeroconf import ServiceInfo, ServiceStateChange
from pytest_mock import MockerFixture

from brewblox_devcon_spark import const, mdns

TESTED = mdns.__name__


class ServiceBrowserMock():

    def __init__(self, conf, service_type, handlers):
        print(conf, service_type, handlers)
        self.conf = conf
        self.service_type = service_type
        self.handlers = handlers

        for name in ['id0', 'id1', 'id2', 'id3']:
            self.handlers[0](conf, service_type, name, ServiceStateChange.Added)
            self.handlers[0](conf, service_type, name, ServiceStateChange.Removed)


@pytest.fixture(autouse=True)
def conf_mock(mocker: MockerFixture) -> Mock:

    async def get_service_info(service_type, name):
        if name == 'id0':
            return ServiceInfo(
                service_type,
                f'{name}.{const.BREWBLOX_DNS_TYPE}',
                address=inet_aton('0.0.0.0'),
                properties={b'ID': name.encode()},
            )
        if name == 'id1':
            return ServiceInfo(
                service_type,
                f'{name}.{const.BREWBLOX_DNS_TYPE}',
                server=f'{name}.local.',
                address=inet_aton('1.2.3.4'),
                port=1234,
                properties={b'ID': name.encode()},
            )
        if name == 'id2':
            return ServiceInfo(
                service_type,
                f'{name}.{const.BREWBLOX_DNS_TYPE}',
                server=f'{name}.local.',
                address=inet_aton('4.3.2.1'),
                port=4321,
                properties={b'ID': name.encode()},
            )
        if name == 'id3':
            return ServiceInfo(
                service_type,
                f'{name}.{const.BREWBLOX_DNS_TYPE}',
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


@pytest.fixture(autouse=True)
def browser_mock(mocker: MockerFixture) -> Mock:
    return mocker.patch(TESTED + '.ServiceBrowser', ServiceBrowserMock)


async def test_discover_one():
    assert await mdns.discover_one(None, const.BREWBLOX_DNS_TYPE, timedelta(seconds=1)) == ('1.2.3.4', 1234, 'id1')
    assert await mdns.discover_one('id2', const.BREWBLOX_DNS_TYPE, timedelta(seconds=1)) == ('4.3.2.1', 4321, 'id2')

    assert await mdns.discover_one(None, const.BREWBLOX_DNS_TYPE, timedelta(seconds=1)) == ('1.2.3.4', 1234, 'id1')
    assert await mdns.discover_one('id2', const.BREWBLOX_DNS_TYPE, timedelta(seconds=1)) == ('4.3.2.1', 4321, 'id2')

    with pytest.raises(asyncio.TimeoutError):
        await mdns.discover_one('leprechauns', const.BREWBLOX_DNS_TYPE, timedelta(milliseconds=10))


async def test_discover_all():
    retv = []
    async for res in mdns.discover_all(None, const.BREWBLOX_DNS_TYPE, timedelta(milliseconds=100)):
        retv.append(res)
    assert len(retv) == 2
