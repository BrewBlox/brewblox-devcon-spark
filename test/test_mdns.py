import asyncio
from datetime import timedelta
from socket import inet_aton
from unittest.mock import AsyncMock, Mock

import pytest
from pytest_mock import MockerFixture
from zeroconf import ServiceStateChange
from zeroconf.asyncio import AsyncServiceInfo

from brewblox_devcon_spark import const, mdns

TESTED = mdns.__name__

# The services the browser announces, in order, with the details a request returns
SERVICES = {
    'id0': {'addresses': [inet_aton('0.0.0.0')], 'port': 8332, 'properties': {b'ID': b'id0'}},  # simulator
    'id1': {'addresses': [inet_aton('1.2.3.4')], 'port': 1234, 'properties': {b'ID': b'id1'}},
    'id2': {'addresses': [inet_aton('4.3.2.1')], 'port': 4321, 'properties': {b'ID': b'id2'}},
    'id3': {'addresses': [inet_aton('4.3.2.1')], 'port': 4321, 'properties': {}},  # no ID: discarded
    'id4': None,  # does not answer the request
}


class ServiceInfoMock(AsyncServiceInfo):
    def __init__(self, type_: str, name: str):
        self.details = SERVICES[name.removesuffix('.' + type_)]
        super().__init__(type_, name, **(self.details or {}))

    async def async_request(self, zc, timeout, question_type=None) -> bool:
        return self.details is not None


class ServiceBrowserMock:
    instances: list['ServiceBrowserMock'] = []

    def __init__(self, zc, type_, handlers, question_type):
        self.cancelled = False
        ServiceBrowserMock.instances.append(self)
        for id in SERVICES:
            for state_change in [ServiceStateChange.Added, ServiceStateChange.Removed]:
                handlers[0](zeroconf=zc, service_type=type_, name=f'{id}.{type_}', state_change=state_change)

    async def async_cancel(self):
        self.cancelled = True


@pytest.fixture(autouse=True)
def zeroconf_mock(mocker: MockerFixture) -> Mock:
    ServiceBrowserMock.instances.clear()
    mocker.patch(TESTED + '.AsyncServiceBrowser', ServiceBrowserMock)
    mocker.patch(TESTED + '.AsyncServiceInfo', ServiceInfoMock)
    m = mocker.patch(TESTED + '.AsyncZeroconf')
    m.return_value.async_close = AsyncMock()
    return m


def closed(zeroconf_mock: Mock) -> bool:
    browsers = ServiceBrowserMock.instances
    closes = zeroconf_mock.return_value.async_close.await_count
    return all(browser.cancelled for browser in browsers) and closes == len(browsers)


async def test_discover_one(zeroconf_mock: Mock):
    assert await mdns.discover_one(None, const.BREWBLOX_DNS_TYPE, timedelta(seconds=1)) == ('1.2.3.4', 1234, 'id1')
    assert await mdns.discover_one('id2', const.BREWBLOX_DNS_TYPE, timedelta(seconds=1)) == ('4.3.2.1', 4321, 'id2')
    assert await mdns.discover_one('ID2', const.BREWBLOX_DNS_TYPE, timedelta(seconds=1)) == ('4.3.2.1', 4321, 'id2')

    with pytest.raises(asyncio.TimeoutError):
        await mdns.discover_one('leprechauns', const.BREWBLOX_DNS_TYPE, timedelta(milliseconds=10))

    # Discovery stops as soon as it returns
    assert closed(zeroconf_mock)


async def test_discover_all(zeroconf_mock: Mock):
    retv = [res async for res in mdns.discover_all(None, const.BREWBLOX_DNS_TYPE, timedelta(milliseconds=100))]
    assert retv == [('1.2.3.4', 1234, 'id1'), ('4.3.2.1', 4321, 'id2')]
    assert closed(zeroconf_mock)
