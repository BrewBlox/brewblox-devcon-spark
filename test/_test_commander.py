"""
Tests brewblox_devcon_spark.commander
"""

import asyncio

import pytest
from brewblox_service import scheduler
from brewblox_service.testing import matching

from brewblox_devcon_spark import (codec, commander, connection,
                                   service_status, service_store)
from brewblox_devcon_spark.models import (ErrorCode, IntermediateResponse,
                                          ServiceConfig)

TESTED = commander.__name__


@pytest.fixture
def setup(app):
    config = utils.get_config()
    config.command_timeout = 1

    service_status.setup(app)
    scheduler.setup(app)
    service_store.setup(app)
    codec.setup(app)
    connection.setup(app)
    commander.setup(app)


async def test_acknowledge(app, client):
    welcome = ','.join([
        '!BREWBLOX',
        'ed70d66f0',
        '3f2243a',
        '2019-06-18',
        '2019-06-18',
        '1.2.1-rc.2',
        'p1',
        '78',
        '0A',
        '1234567F0CASE'
    ])
    service_status.set_enabled(app, True)
    await asyncio.wait_for(service_status.wait_connected(app), timeout=5)
    assert not service_status.is_acknowledged(app)

    with pytest.warns(UserWarning, match='incompatible device ID'):
        await connection.fget(app).on_event(welcome)

    assert service_status.is_acknowledged(app)
    assert service_status.desc(app).controller.device.device_id == '1234567f0case'


async def test_unexpected_event(app, client, mocker):
    m_log_info = mocker.patch(TESTED + '.LOGGER.info', autospec=True)
    await connection.fget(app).on_event('hello world!')
    m_log_info.assert_called_with(matching(r'.*hello world!'))


async def test_unexpected_response(app, client, mocker):
    m_log_error = mocker.patch(TESTED + '.LOGGER.error', autospec=True)
    response = IntermediateResponse(
        msgId=123,
        error=ErrorCode.OK,
        payload=[]
    )
    message = codec.fget(app).encode_response(response)
    await connection.fget(app).on_response(message)
    m_log_error.assert_called_with(matching(r'.*Unexpected message'))


async def test_firmware_update_call(app, client, mocker):
    # We don't unit test OTA update logic because it makes very in-depth assumptions
    # about how particle devices respond to YMODEM calls
    # We'll check now whether the basic call works
    service_status.set_enabled(app, True)
    await asyncio.wait_for(service_status.wait_connected(app), timeout=5)
    await commander.fget(app).firmware_update()
