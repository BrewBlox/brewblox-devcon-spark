import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI

from brewblox_devcon_spark import codec, command, connection, exceptions, state_machine, utils
from brewblox_devcon_spark.connection import connection_handler
from brewblox_devcon_spark.models import (
    ControllerDescription,
    DeviceDescription,
    ErrorCode,
    FirmwareDescription,
    IntermediateResponse,
    ResetReason,
)

TESTED = command.__name__

WELCOME = ','.join(
    [
        '!BREWBLOX',
        'ed70d66f0',
        '3f2243a',
        '2019-06-18',
        '2019-06-18',
        '1.2.1-rc.2',
        'p1',
        '78',
        '0A',
        '1234567F0CASE',
    ]
)


def controller_desc() -> ControllerDescription:
    config = utils.get_config()
    fw_config = utils.get_fw_config()

    return ControllerDescription(
        system_version='1.23',
        platform='mock',
        reset_reason=ResetReason.NONE.value,
        firmware=FirmwareDescription(
            firmware_version=fw_config.firmware_version,
            proto_version=fw_config.proto_version,
            firmware_date=fw_config.firmware_date,
            proto_date=fw_config.proto_date,
        ),
        device=DeviceDescription(
            device_id=config.device_id,
        ),
    )


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
    command.setup()
    return FastAPI(lifespan=lifespan)


async def test_acknowledge(manager: LifespanManager):
    welcome = ','.join(
        [
            '!BREWBLOX',
            'ed70d66f0',
            '3f2243a',
            '2019-06-18',
            '2019-06-18',
            '1.2.1-rc.2',
            'p1',
            '78',
            '0A',
            '1234567F0CASE',
        ]
    )
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


async def test_pre_handshake_garbage(caplog: pytest.LogCaptureFixture):
    """Garbage messages received before handshake are ignored silently."""
    state = state_machine.CV.get()
    assert not state.is_acknowledged()

    # Send invalid/garbage message before handshake
    await connection.CV.get().on_response('garbage data that cannot be decoded')

    record = caplog.records[-1]
    assert record.levelname == 'DEBUG'
    assert 'pre-handshake' in record.message


async def test_post_handshake_garbage(manager: LifespanManager, caplog: pytest.LogCaptureFixture):
    """
    Post-handshake decode failures should be rare (atomic framed writes in firmware).
    When they do happen we want them loud — WARNING, not hidden.
    """
    from brewblox_devcon_spark.models import ControllerDescription, DeviceDescription, FirmwareDescription, ResetReason

    config = utils.get_config()
    fw_config = utils.get_fw_config()

    desc = ControllerDescription(
        system_version='1.23',
        platform='mock',
        reset_reason=ResetReason.NONE.value,
        firmware=FirmwareDescription(
            firmware_version=fw_config.firmware_version,
            proto_version=fw_config.proto_version,
            firmware_date=fw_config.firmware_date,
            proto_date=fw_config.proto_date,
        ),
        device=DeviceDescription(
            device_id=config.device_id,
        ),
    )

    state = state_machine.CV.get()
    state.set_enabled(True)
    await asyncio.wait_for(state.wait_connected(), timeout=5)

    state.set_acknowledged(desc)
    assert state.is_acknowledged()

    await connection.CV.get().on_response('garbage data that cannot be decoded')

    record = caplog.records[-1]
    assert record.levelname == 'WARNING'
    assert 'unsolicited message' in record.message


async def test_unexpected_response(caplog: pytest.LogCaptureFixture):
    """A cleanly-decoded response with no matching in-flight msgId is surfaced at WARNING."""
    response = IntermediateResponse(msgId=123, error=ErrorCode.OK, payload=[])
    message = codec.CV.get().encode_response(response)
    await connection.CV.get().on_response(message)

    record = caplog.records[-1]
    assert record.levelname == 'WARNING'
    assert 'Unexpected message' in record.message


async def test_firmware_update_call(manager: LifespanManager):
    # We don't unit test OTA update logic because it makes very in-depth assumptions
    # about how particle devices respond to YMODEM calls
    # We'll check now whether the basic call works
    state = state_machine.CV.get()
    cmdr = command.CV.get()

    state.set_enabled(True)
    await asyncio.wait_for(state.wait_connected(), timeout=5)
    await cmdr.firmware_update()
    await cmdr.wait_empty()


async def test_handshake_resets_stale_commands(manager: LifespanManager):
    """
    The first handshake of a session discards commands left in flight by the
    previous session, so their callers fail fast instead of waiting out
    command_timeout. The NONE/VERSION command that solicited the handshake
    is left alone: its own reply is still on its way.
    """
    state = state_machine.CV.get()
    cmdr = command.CV.get()

    state.set_enabled(True)
    await asyncio.wait_for(state.wait_connected(), timeout=5)
    assert not state.is_acknowledged()

    loop = asyncio.get_running_loop()
    stale_fut = loop.create_future()
    resolved_fut = loop.create_future()
    solicited_fut = loop.create_future()

    # A block command left over from a previous session ...
    cmdr._active_messages[901] = stale_fut
    # ... one whose response landed before its caller was scheduled again ...
    resolved_fut.set_result(IntermediateResponse(msgId=900, error=ErrorCode.OK, payload=[]))
    cmdr._active_messages[900] = resolved_fut
    # ... and the version prompt that is about to be answered by this handshake
    cmdr._active_messages[902] = solicited_fut
    cmdr._handshake_msgids.add(902)

    await connection.CV.get().on_event(WELCOME)

    assert 901 not in cmdr._active_messages
    with pytest.raises(exceptions.ConnectionException):
        stale_fut.result()

    # An already-resolved future is dropped, but keeps its result for its caller
    assert 900 not in cmdr._active_messages
    assert resolved_fut.result().msgId == 900

    assert 902 in cmdr._active_messages
    assert not solicited_fut.done()

    # Cleanup: the commander is a session-scoped singleton
    cmdr._active_messages.clear()
    cmdr._handshake_msgids.clear()


async def test_solicited_handshake_keeps_session(manager: LifespanManager):
    """
    The controller also sends a handshake in reply to NONE/VERSION.
    Once acknowledged, such a handshake must not discard in-flight commands.
    """
    state = state_machine.CV.get()
    cmdr = command.CV.get()

    state.set_enabled(True)
    await asyncio.wait_for(state.wait_connected(), timeout=5)
    state.set_acknowledged(controller_desc())

    loop = asyncio.get_running_loop()
    fut = loop.create_future()
    cmdr._active_messages[903] = fut

    await connection.CV.get().on_event(WELCOME)

    assert 903 in cmdr._active_messages
    assert not fut.done()

    cmdr._active_messages.clear()


async def test_decode_error_fails_in_flight(manager: LifespanManager, caplog: pytest.LogCaptureFixture):
    """
    A post-handshake decode error means the stream is desynced.
    In-flight commands fail immediately rather than waiting for command_timeout.
    """
    state = state_machine.CV.get()
    cmdr = command.CV.get()

    state.set_enabled(True)
    await asyncio.wait_for(state.wait_connected(), timeout=5)
    state.set_acknowledged(controller_desc())

    fut = asyncio.get_running_loop().create_future()
    cmdr._active_messages[904] = fut

    await connection.CV.get().on_response('garbage data that cannot be decoded')

    assert 904 not in cmdr._active_messages
    with pytest.raises(exceptions.ConnectionException):
        fut.result()

    record = caplog.records[-1]
    assert record.levelname == 'WARNING'
    assert 'failing 1 in-flight command(s)' in record.message


def test_error_codes_match_proto():
    """Every error code the firmware can send must be known, or its reply is treated as a decode error."""
    from brewblox_devcon_spark.codec.pb2 import command_pb2

    assert {code.name: code.value for code in ErrorCode} == dict(command_pb2.ErrorCode.items())
