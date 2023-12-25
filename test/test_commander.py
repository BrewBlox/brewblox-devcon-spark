"""
Tests brewblox_devcon_spark.commander
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta

import pytest
from fastapi import FastAPI

from brewblox_devcon_spark import (codec, commander, connection, state_machine,
                                   utils)
from brewblox_devcon_spark.connection import connection_handler
from brewblox_devcon_spark.models import ErrorCode, IntermediateResponse

TESTED = commander.__name__


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with connection_handler.lifespan():
        yield


@pytest.fixture(autouse=True)
def app() -> FastAPI:
    config = utils.get_config()
    config.command_timeout = timedelta(seconds=1)

    state_machine.setup()
    codec.setup()
    connection_handler.setup()
    commander.setup()
    return FastAPI(lifespan=lifespan)


async def test_acknowledge():
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
    state = state_machine.CV.get()
    conn = connection.CV.get()

    state.set_enabled(True)
    await asyncio.wait_for(state.wait_connected(), timeout=5)
    assert not state.is_acknowledged()

    await conn.on_event(welcome)
    assert state.desc().firmware_error == 'INCOMPATIBLE'

    assert state.is_acknowledged()
    assert state.desc().controller.device.device_id == '1234567f0case'


async def test_unexpected_event(caplog: pytest.LogCaptureFixture):
    await connection.CV.get().on_event('hello world!')
    record = caplog.records[-1]
    assert record.levelname == 'INFO'
    assert 'hello world' in record.message


async def test_unexpected_response(caplog: pytest.LogCaptureFixture):
    response = IntermediateResponse(
        msgId=123,
        error=ErrorCode.OK,
        payload=[]
    )
    message = codec.CV.get().encode_response(response)
    await connection.CV.get().on_response(message)

    record = caplog.records[-1]
    assert record.levelname == 'ERROR'
    assert 'Unexpected message' in record.message


async def test_firmware_update_call(client, mocker):
    # We don't unit test OTA update logic because it makes very in-depth assumptions
    # about how particle devices respond to YMODEM calls
    # We'll check now whether the basic call works
    state = state_machine.CV.get()
    cmdr = commander.CV.get()

    state.set_enabled(True)
    await asyncio.wait_for(state.wait_connected(), timeout=5)
    await cmdr.firmware_update()
