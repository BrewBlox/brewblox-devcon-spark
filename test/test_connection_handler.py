"""
Tests brewblox_devcon_spark.connection.connection_handler
"""


import asyncio
from unittest.mock import AsyncMock

import pytest
from brewblox_service import scheduler

from brewblox_devcon_spark import exceptions, service_status, service_store
from brewblox_devcon_spark.codec import unit_conversion
from brewblox_devcon_spark.connection import connection_handler
from brewblox_devcon_spark.models import DiscoveryType, ServiceConfig

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


@pytest.fixture
async def setup(app):
    service_status.setup(app)
    scheduler.setup(app)
    service_store.setup(app)
    unit_conversion.setup(app)


async def test_calc_backoff():
    assert connection_handler.calc_backoff(0) == connection_handler.BASE_RECONNECT_DELAY_S
    assert connection_handler.calc_backoff(None) == connection_handler.BASE_RECONNECT_DELAY_S
    assert connection_handler.calc_backoff(1) == pytest.approx(2)
    assert connection_handler.calc_backoff(2) == pytest.approx(3)
    assert connection_handler.calc_backoff(10) == pytest.approx(15)
    assert connection_handler.calc_backoff(60) == connection_handler.MAX_RECONNECT_DELAY_S


async def test_usb_compatible(app, client, mocker):
    config: ServiceConfig = app['config']
    handler = connection_handler.ConnectionHandler(app)

    # Set all relevant settings to default
    def reset():
        config.discovery = DiscoveryType.all
        config.device_serial = None
        config.device_host = None
        config.device_id = None
        config.simulation = False
        config.mock = False

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


async def test_handler_discovery(app, client, mocker):
    mocker.patch(TESTED + '.DISCOVERY_INTERVAL_S', 0)

    config: ServiceConfig = app['config']
    m_discover_usb: AsyncMock = mocker.patch(TESTED + '.discover_usb', autospec=True)
    m_discover_mdns: AsyncMock = mocker.patch(TESTED + '.discover_mdns', autospec=True)
    m_discover_mqtt: AsyncMock = mocker.patch(TESTED + '.discover_mqtt', autospec=True)

    def reset():
        m_discover_usb.reset_mock()
        m_discover_mdns.reset_mock()
        m_discover_mqtt.reset_mock()

        m_discover_usb.side_effect = None
        m_discover_mdns.side_effect = None
        m_discover_mqtt.side_effect = None

    handler = connection_handler.ConnectionHandler(app)

    # Discovery order is USB -> mDNS -> MQTT
    config.discovery = DiscoveryType.all

    await handler.discover()
    m_discover_usb.assert_awaited_once_with(app, handler)
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
    mocker.patch(TESTED + '.DISCOVERY_TIMEOUT_S', 0.01)

    config.discovery = DiscoveryType.all
    m_discover_usb.return_value = None
    m_discover_mdns.return_value = None
    m_discover_mqtt.return_value = None

    with pytest.raises(ConnectionAbortedError):
        await handler.discover()


async def test_handler_connect_order(app, client, mocker):
    config: ServiceConfig = app['config']
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

    handler = connection_handler.ConnectionHandler(app)

    # Lowest prio: discovery
    # Discovery order is serial -> TCP -> MQTT
    config.mock = False
    config.simulation = False
    config.device_serial = None
    config.device_host = None
    config.discovery = DiscoveryType.all
    config.device_id = '01ab23ce'

    await handler.connect()

    m_funcs['discover_usb'].assert_awaited_once_with(app, handler)
    for f in without('discover_usb'):
        f.assert_not_awaited()

    reset()

    # If host is set, TCP takes precedence over discovery
    config.device_host = 'hostface'
    config.device_port = 1234

    await handler.connect()

    m_funcs['connect_tcp'].assert_awaited_once_with(app, handler, 'hostface', 1234)
    for f in without('connect_tcp'):
        f.assert_not_awaited()

    reset()

    # If serial is set, it takes precedence over TCP
    config.device_serial = 'serialface'

    await handler.connect()

    m_funcs['connect_usb'].assert_awaited_once_with(app, handler, 'serialface')
    for f in without('connect_usb'):
        f.assert_not_awaited()

    reset()

    # If simulation is set, it takes precedence over serial
    config.simulation = True

    await handler.connect()

    m_funcs['connect_simulation'].assert_awaited_once_with(app, handler)
    for f in without('connect_simulation'):
        f.assert_not_awaited()

    reset()

    # If mock is set, it takes precedence over simulation
    config.mock = True

    await handler.connect()

    m_funcs['connect_mock'].assert_awaited_once_with(app, handler)
    for f in without('connect_mock'):
        f.assert_not_awaited()


async def test_handler_run(app, client):
    handler = connection_handler.ConnectionHandler(app)
    handler.on_response = AsyncMock()

    with pytest.raises(exceptions.NotConnected):
        await handler.send_request('')

    runner = asyncio.create_task(handler.run())

    service_status.set_enabled(app, True)
    await asyncio.wait_for(service_status.wait_connected(app),
                           timeout=5)

    # We're assuming here that mock_connection.send_request()
    # immediately calls the on_response() callback
    await handler.send_request('')
    handler.on_response.assert_awaited_once()

    assert not runner.done()
    runner.cancel()


async def test_handler_disconnect(app, client, mocker):
    handler = connection_handler.ConnectionHandler(app)

    # can safely be called when not connected
    await handler.start_reconnect()

    service_status.set_enabled(app, True)

    runner = asyncio.create_task(handler.run())
    await asyncio.wait_for(service_status.wait_connected(app),
                           timeout=5)

    await handler.start_reconnect()

    # If connection signals closed, handler cleanly stops its run
    # and calls service_status.set_disconnected()
    await asyncio.wait_for(runner, timeout=5)
    assert runner.exception() is None
    assert service_status.is_disconnected(app)


async def test_handler_connect_error(app, client, mocker):
    mocker.patch(TESTED + '.web.GracefulExit', DummyExit)
    mocker.patch(TESTED + '.calc_backoff').return_value = 0.0001
    m_connect_mock: AsyncMock = mocker.patch(TESTED + '.connect_mock', autospec=True)
    m_connect_mock.side_effect = ConnectionRefusedError

    service_status.set_enabled(app, True)

    handler = connection_handler.ConnectionHandler(app)

    # Retry until attempts exhausted
    # This is a mock - it will not attempt to restart the service
    for _ in range(connection_handler.MAX_RETRY_COUNT * 2):
        await handler.run()

    # It immediately threw a connection abort once the retry count was exceeded
    assert m_connect_mock.await_count == connection_handler.MAX_RETRY_COUNT * 2 - 1


async def test_handler_discovery_error(app, client, mocker):
    mocker.patch(TESTED + '.web.GracefulExit', DummyExit)
    mocker.patch(TESTED + '.DISCOVERY_INTERVAL_S', 0.001)
    mocker.patch(TESTED + '.DISCOVERY_TIMEOUT_S', 0.01)

    m_discover_usb = mocker.patch(TESTED + '.discover_usb', autospec=True)
    m_discover_usb.return_value = None

    config: ServiceConfig = app['config']
    config.mock = False
    config.simulation = False
    config.device_serial = None
    config.device_host = None
    config.discovery = DiscoveryType.usb

    service_status.set_enabled(app, True)

    handler = connection_handler.ConnectionHandler(app)
    with pytest.raises(DummyExit):
        await handler.run()

    assert service_store.get_reconnect_delay(app) > 0
    service_store.set_reconnect_delay(app, 0)

    # No reboot is required when discovery does not involve USB
    m_discover_mqtt = mocker.patch(TESTED + '.discover_mqtt', autospec=True)
    m_discover_mqtt.return_value = None
    config.discovery = DiscoveryType.mqtt

    # No error, only a silent exit
    await handler.run()
