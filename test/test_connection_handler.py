"""
Tests brewblox_devcon_spark.connection.connection_handler
"""


import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from pytest_mock import MockerFixture

from brewblox_devcon_spark import exceptions, state_machine, utils
from brewblox_devcon_spark.codec import unit_conversion
from brewblox_devcon_spark.connection import connection_handler
from brewblox_devcon_spark.models import DiscoveryType

TESTED = connection_handler.__name__


class DummyExit(Exception):
    pass


def welcome_message():
    return [
        'BREWBLOX',
        'ed70d66f0',
        '3f2243a',
        '2019-06-18',
        '2019-06-18',
        '1.2.1-rc.2',
        'p1',
        '78',
        '0A',
        '1234567f0case'
    ]


@pytest.fixture(autouse=True)
def app() -> FastAPI:
    state_machine.setup()
    unit_conversion.setup()
    return FastAPI()


@pytest.mark.parametrize('value,expected', [
    (timedelta(), timedelta(seconds=2)),
    (None, timedelta(seconds=2)),
    (timedelta(seconds=1), timedelta(seconds=1, milliseconds=500)),
    (timedelta(seconds=2), timedelta(seconds=3)),
    (timedelta(seconds=10), timedelta(seconds=15)),
    (timedelta(minutes=1), timedelta(seconds=30)),
])
async def test_calc_interval(value: timedelta | None, expected: timedelta):
    config = utils.get_config()
    config.connect_interval = timedelta(seconds=2)
    config.connect_interval_max = timedelta(seconds=30)

    assert connection_handler.calc_interval(value) == expected


async def test_usb_compatible():
    config = utils.get_config()
    handler = connection_handler.ConnectionHandler()

    # Set all relevant settings to default
    def reset():
        config.discovery = DiscoveryType.all
        config.device_serial = None
        config.device_host = None
        config.device_id = None
        config.simulation = False
        config.mock = False
        config.discovery_timeout = timedelta(seconds=10)

    # The default is to enable USB
    reset()
    assert handler.usb_compatible

    reset()
    config.mock = True
    assert not handler.usb_compatible

    reset()
    config.device_host = 'localhost'
    assert not handler.usb_compatible

    reset()
    config.discovery = DiscoveryType.lan
    assert not handler.usb_compatible

    reset()
    config.discovery = DiscoveryType.usb
    assert handler.usb_compatible

    # Positive identification of Spark 4 ID
    reset()
    config.discovery = DiscoveryType.all
    config.device_id = 'x'*12
    assert not handler.usb_compatible


async def test_handler_discovery(mocker: MockerFixture):
    config = utils.get_config()
    m_discover_usb: AsyncMock = mocker.patch(TESTED + '.discover_usb', autospec=True)
    m_discover_mdns: AsyncMock = mocker.patch(TESTED + '.discover_mdns', autospec=True)
    m_discover_mqtt: AsyncMock = mocker.patch(TESTED + '.discover_mqtt', autospec=True)

    def reset():
        config.discovery = DiscoveryType.all
        config.device_id = '1234'
        config.discovery_interval = timedelta()
        config.discovery_timeout = timedelta(seconds=1)

        m_discover_usb.reset_mock()
        m_discover_mdns.reset_mock()
        m_discover_mqtt.reset_mock()

        m_discover_usb.side_effect = None
        m_discover_mdns.side_effect = None
        m_discover_mqtt.side_effect = None

    handler = connection_handler.ConnectionHandler()

    # Discovery order is USB -> mDNS -> MQTT
    config.discovery = DiscoveryType.all

    await handler.discover()
    m_discover_usb.assert_awaited_once_with(handler)
    m_discover_mdns.assert_not_awaited()
    m_discover_mqtt.assert_not_awaited()

    reset()

    # Only discover mDNS
    config.discovery = DiscoveryType.mdns
    m_discover_mdns.return_value = 'tcp_result'

    assert await handler.discover() == 'tcp_result'
    m_discover_usb.assert_not_awaited()
    m_discover_mqtt.assert_not_awaited()

    reset()

    # Only discover MQTT
    config.discovery = DiscoveryType.mqtt
    m_discover_mqtt.return_value = 'mqtt_result'

    assert await handler.discover() == 'mqtt_result'
    m_discover_usb.assert_not_awaited()
    m_discover_mdns.assert_not_awaited()

    reset()

    # Retry if discovery fails the first time
    config.discovery = DiscoveryType.mdns
    m_discover_mdns.side_effect = [None, None, 'tcp_result']

    assert await handler.discover() == 'tcp_result'
    assert m_discover_mdns.await_count == 3
    m_discover_usb.assert_not_awaited()
    m_discover_mqtt.assert_not_awaited()

    reset()

    # Throw a timeout error after a while
    config.discovery_timeout = timedelta(milliseconds=1)
    config.discovery = DiscoveryType.all
    m_discover_usb.return_value = None
    m_discover_mdns.return_value = None
    m_discover_mqtt.return_value = None

    with pytest.raises(ConnectionAbortedError):
        await handler.discover()


async def test_handler_connect_order(mocker: MockerFixture):
    config = utils.get_config()
    m_funcs: dict[str, AsyncMock] = {
        k: mocker.patch(f'{TESTED}.{k}', autospec=True)
        for k in [
            'connect_mock',
            'connect_simulation',
            'connect_usb',
            'connect_tcp',
            'discover_usb',
            'discover_mdns',
            'discover_mqtt'
        ]
    }

    def without(*names: list[str]) -> list[AsyncMock]:
        return [f for k, f in m_funcs.items() if k not in names]

    def reset():
        for f in m_funcs.values():
            f.reset_mock()

    handler = connection_handler.ConnectionHandler()

    # Lowest prio: discovery
    # Discovery order is serial -> TCP -> MQTT
    config.mock = False
    config.simulation = False
    config.device_serial = None
    config.device_host = None
    config.discovery = DiscoveryType.all
    config.device_id = '01ab23ce'

    await handler.connect()

    m_funcs['discover_usb'].assert_awaited_once_with(handler)
    for f in without('discover_usb'):
        f.assert_not_awaited()

    reset()

    # If host is set, TCP takes precedence over discovery
    config.device_host = 'hostface'
    config.device_port = 1234

    await handler.connect()

    m_funcs['connect_tcp'].assert_awaited_once_with(handler, 'hostface', 1234)
    for f in without('connect_tcp'):
        f.assert_not_awaited()

    reset()

    # If serial is set, it takes precedence over TCP
    config.device_serial = 'serialface'

    await handler.connect()

    m_funcs['connect_usb'].assert_awaited_once_with(handler, 'serialface')
    for f in without('connect_usb'):
        f.assert_not_awaited()

    reset()

    # If simulation is set, it takes precedence over serial
    config.simulation = True

    await handler.connect()

    m_funcs['connect_simulation'].assert_awaited_once_with(handler)
    for f in without('connect_simulation'):
        f.assert_not_awaited()

    reset()

    # If mock is set, it takes precedence over simulation
    config.mock = True

    await handler.connect()

    m_funcs['connect_mock'].assert_awaited_once_with(handler)
    for f in without('connect_mock'):
        f.assert_not_awaited()


async def test_handler_run():
    config = utils.get_config()
    state = state_machine.CV.get()
    handler = connection_handler.ConnectionHandler()

    handler.on_response = AsyncMock()
    config.mock = True

    with pytest.raises(exceptions.NotConnected):
        await handler.send_request('')

    async with utils.task_context(handler.run()) as task:
        state.set_enabled(True)
        await asyncio.wait_for(state.wait_connected(),
                               timeout=5)

        # We're assuming here that mock_connection.send_request()
        # immediately calls the on_response() callback
        await handler.send_request('')
        handler.on_response.assert_awaited_once()
        assert not task.done()


async def test_handler_disconnect(mocker: MockerFixture):
    config = utils.get_config()
    state = state_machine.CV.get()
    handler = connection_handler.ConnectionHandler()

    config.mock = True

    # can safely be called when not connected
    await handler.reset()

    state.set_enabled(True)

    async with utils.task_context(handler.run()) as task:
        await asyncio.wait_for(state.wait_connected(),
                               timeout=5)

        await handler.reset()

        # If connection signals closed, handler cleanly stops its run
        # and calls state.set_disconnected()
        await asyncio.wait([task], timeout=5)
        assert task.exception() is None
        assert state.is_disconnected()


async def test_handler_connect_error(mocker: MockerFixture, m_kill: Mock):
    m_connect_mock: AsyncMock = mocker.patch(TESTED + '.connect_mock', autospec=True)
    m_connect_mock.side_effect = ConnectionRefusedError

    config = utils.get_config()
    state = state_machine.CV.get()
    handler = connection_handler.ConnectionHandler()

    config.mock = True
    state.set_enabled(True)

    # Retry until attempts exhausted
    # This is a mock - it will not attempt to restart the service
    for _ in range(connection_handler.MAX_RETRY_COUNT * 2):
        await handler.run()

    m_kill.assert_not_called()

    # It immediately threw a connection abort once the retry count was exceeded
    assert m_connect_mock.await_count == connection_handler.MAX_RETRY_COUNT * 2 - 1


async def test_handler_discovery_error(mocker: MockerFixture, m_kill: Mock):
    m_discover_usb = mocker.patch(TESTED + '.discover_usb', autospec=True)
    m_discover_usb.return_value = None

    config = utils.get_config()
    config.mock = False
    config.simulation = False
    config.device_serial = None
    config.device_host = None
    config.discovery = DiscoveryType.usb
    config.discovery_interval = timedelta()
    config.discovery_timeout = timedelta(milliseconds=1)

    state = state_machine.CV.get()

    state.set_enabled(True)

    handler = connection_handler.ConnectionHandler()
    m_kill.side_effect = RuntimeError
    with pytest.raises(RuntimeError):
        await handler.run()

    # No reboot is required when discovery does not involve USB
    m_discover_mqtt = mocker.patch(TESTED + '.discover_mqtt', autospec=True)
    m_discover_mqtt.return_value = None
    config.discovery = DiscoveryType.mqtt

    # No error, only a silent exit
    await handler.run()
