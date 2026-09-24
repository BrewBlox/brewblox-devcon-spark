import asyncio
import time
from contextlib import asynccontextmanager
from datetime import timedelta

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from pytest_mock import MockerFixture

from brewblox_devcon_spark import codec, command, connection, exceptions, state_machine, utils
from brewblox_devcon_spark.command import BlockChange
from brewblox_devcon_spark.connection import connection_handler, mock_connection
from brewblox_devcon_spark.models import (
    ControllerDescription,
    DecodedPayload,
    DeviceDescription,
    ErrorCode,
    FirmwareBlock,
    FirmwareBlockIdentity,
    FirmwareDescription,
    IntermediateResponse,
    Opcode,
    ReadMode,
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

    changes: list[BlockChange] = []
    cmdr.on_block_change = changes.append
    cmdr._handshake_msgids.add(903)

    await connection.CV.get().on_event(WELCOME)

    assert 903 in cmdr._active_messages
    assert not fut.done()

    # Solicited: not a sign of a controller reboot
    assert changes == []

    cmdr._active_messages.clear()
    cmdr._handshake_msgids.clear()


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


async def connected() -> command.CboxCommander:
    state = state_machine.CV.get()
    state.set_enabled(True)
    await asyncio.wait_for(state.wait_connected(), timeout=5)
    return command.CV.get()


def sensor(nid: int = 0, **data) -> FirmwareBlock:
    return FirmwareBlock(id='sensor', nid=nid, type='TempSensorMock', data=data)


async def wait_sent(cmdr: command.CboxCommander):
    """Waits until a request is waiting for its response"""
    while not cmdr._active_messages:
        await asyncio.sleep(0)


async def test_block_listener(manager: LifespanManager):
    """
    Requests that change blocks or read them all notify the block listener,
    in send order, with the session they were sent in.
    """
    state = state_machine.CV.get()
    cmdr = await connected()

    changes: list[BlockChange] = []
    cmdr.on_block_change = changes.append

    created = await cmdr.create_block(sensor(setting=20))
    await cmdr.write_block(sensor(created.nid, setting=21))
    await cmdr.patch_block(sensor(created.nid, setting=22))
    await cmdr.noop()  # Not a block change
    await cmdr.read_all_blocks()
    changed = await cmdr.read_all_blocks(ReadMode.CHANGED)
    await cmdr.read_all_blocks(ReadMode.STORED)
    await cmdr.discover_blocks()
    await cmdr.delete_block(FirmwareBlockIdentity(nid=created.nid))
    await cmdr.clear_blocks()

    assert [(v.opcode, v.mode) for v in changes] == [
        (Opcode.BLOCK_CREATE, ReadMode.DEFAULT),
        (Opcode.BLOCK_WRITE, ReadMode.DEFAULT),
        (Opcode.BLOCK_WRITE, ReadMode.DEFAULT),
        (Opcode.BLOCK_READ_ALL, ReadMode.DEFAULT),
        (Opcode.BLOCK_READ_ALL, ReadMode.CHANGED),
        (Opcode.BLOCK_READ_ALL, ReadMode.STORED),
        (Opcode.BLOCK_DISCOVER, ReadMode.DEFAULT),
        (Opcode.BLOCK_DELETE, ReadMode.DEFAULT),
        (Opcode.CLEAR_BLOCKS, ReadMode.DEFAULT),
    ]
    assert all(v.error is None for v in changes)
    assert all(v.session == state.session for v in changes)

    # Every request gets a send sequence number, including those that do not notify
    seqs = [v.seq for v in changes]
    assert seqs == sorted(seqs)
    assert seqs[3] == seqs[2] + 2
    assert cmdr._seq == seqs[-1]

    # The listener gets the decoded blocks the caller gets
    assert changes[0].blocks == [created]
    assert changes[1].blocks[0].data['setting']['value'] == 21
    assert changes[1].nid == created.nid
    assert changes[4].blocks == changed
    assert not changed[0].id  # CHANGED reads have no names
    assert changes[7].nid == created.nid
    assert changes[7].blocks == []

    # Without a listener, requests work as before
    cmdr.on_block_change = None
    await cmdr.read_all_blocks()
    assert len(changes) == 9


async def test_block_listener_errors(manager: LifespanManager):
    """
    Failed requests notify the listener before the error is raised.
    Error responses keep their payloads: a read-all may fail halfway.
    """
    cmdr = await connected()
    ccodec = codec.CV.get()
    conn = connection.CV.get()

    changes: list[BlockChange] = []
    cmdr.on_block_change = changes.append

    # Error response
    with pytest.raises(exceptions.CommandException, match='INVALID_BLOCK_ID'):
        await cmdr.write_block(sensor(1234, setting=20))
    assert changes[-1].opcode == Opcode.BLOCK_WRITE
    assert changes[-1].nid == 1234
    assert changes[-1].error == 'INVALID_BLOCK_ID'

    # No response
    utils.get_config().command_timeout = timedelta(milliseconds=10)
    mock_connection.NEXT_ERROR.append(None)
    with pytest.raises(exceptions.CommandTimeout):
        await cmdr.delete_block(FirmwareBlockIdentity(nid=1234))
    assert changes[-1].opcode == Opcode.BLOCK_DELETE
    assert 'CommandTimeout' in changes[-1].error

    # An error response with the payloads that were read before the error
    utils.get_config().command_timeout = timedelta(seconds=1)
    mock_connection.NEXT_ERROR.append(None)
    task = asyncio.create_task(cmdr.read_all_blocks(ReadMode.CHANGED))
    await wait_sent(cmdr)
    payload = ccodec.encode_payload(DecodedPayload(blockId=100, blockType='TempSensorMock', content={'setting': 21}))
    response = IntermediateResponse(
        msgId=cmdr._msgid,
        error=ErrorCode.INSUFFICIENT_HEAP,
        mode=ReadMode.CHANGED,
        payload=[payload],
    )
    await conn.on_response(ccodec.encode_response(response))

    with pytest.raises(exceptions.CommandException, match='INSUFFICIENT_HEAP'):
        await task

    change = changes[-1]
    assert change.opcode == Opcode.BLOCK_READ_ALL
    assert change.mode == ReadMode.CHANGED
    assert change.error == 'INSUFFICIENT_HEAP'
    assert [v.nid for v in change.blocks] == [100]
    assert change.blocks[0].data['setting']['value'] == 21


async def test_block_listener_session(manager: LifespanManager):
    """The listener gets the session a request was sent in, also if the response came in another one"""
    state = state_machine.CV.get()
    cmdr = await connected()
    ccodec = codec.CV.get()
    conn = connection.CV.get()

    changes: list[BlockChange] = []
    cmdr.on_block_change = changes.append
    session = state.session

    mock_connection.NEXT_ERROR.append(None)
    task = asyncio.create_task(cmdr.read_all_blocks(ReadMode.CHANGED, timeout=timedelta(seconds=1)))
    await wait_sent(cmdr)
    state.session += 1

    response = IntermediateResponse(msgId=cmdr._msgid, error=ErrorCode.OK, mode=ReadMode.CHANGED, payload=[])
    await conn.on_response(ccodec.encode_response(response))
    assert await task == []
    assert changes[-1].session == session


async def test_request_timeout(manager: LifespanManager, mocker: MockerFixture):
    """A request can have a shorter timeout than command_timeout"""
    config = utils.get_config()
    cmdr = await connected()
    m_asyncio = mocker.patch.object(command, 'asyncio', wraps=asyncio)

    mock_connection.NEXT_ERROR.append(None)
    start = time.monotonic()
    with pytest.raises(exceptions.CommandTimeout):
        await cmdr.read_all_blocks(ReadMode.CHANGED, timeout=timedelta(milliseconds=10))
    assert time.monotonic() - start < 0.5
    assert m_asyncio.wait_for.call_args.kwargs['timeout'] == 0.01

    # The default is command_timeout.
    # The mock answers before the request waits: the timeout it waits with is checked instead.
    blocks = await cmdr.read_all_blocks(ReadMode.CHANGED)
    assert blocks
    assert m_asyncio.wait_for.call_args.kwargs['timeout'] == config.command_timeout.total_seconds()
    assert config.command_timeout != config.broadcast_timeout


async def test_block_listener_late_response(manager: LifespanManager):
    """A response without a waiting request may have changed blocks"""
    state = state_machine.CV.get()
    cmdr = await connected()
    await cmdr.noop()

    changes: list[BlockChange] = []
    cmdr.on_block_change = changes.append

    response = IntermediateResponse(msgId=123, error=ErrorCode.OK, payload=[])
    await connection.CV.get().on_response(codec.CV.get().encode_response(response))

    assert changes == [BlockChange(cmdr._seq, state.session, None, error='late response')]


async def test_block_listener_handshake(manager: LifespanManager):
    """
    An unsolicited handshake after the first one of a session means the controller rebooted.
    The link stayed up, so the session is the same, but blocks may have changed.
    """
    state = state_machine.CV.get()
    cmdr = await connected()

    changes: list[BlockChange] = []
    cmdr.on_block_change = changes.append

    # The first handshake of a session
    await connection.CV.get().on_event(WELCOME)
    assert state.is_acknowledged()
    assert changes == []

    await connection.CV.get().on_event(WELCOME)
    assert changes == [BlockChange(cmdr._seq, state.session, None, error='unsolicited handshake')]


async def test_block_listener_exception(manager: LifespanManager, caplog: pytest.LogCaptureFixture):
    """A failing listener does not fail the request"""
    cmdr = await connected()

    def listener(change: BlockChange):
        raise RuntimeError('listener bug')

    cmdr.on_block_change = listener
    created = await cmdr.create_block(sensor(setting=20))
    assert created.nid

    record = next(v for v in caplog.records if 'Block listener failed' in v.message)
    assert record.levelname == 'ERROR'
    assert 'listener bug' in record.message
