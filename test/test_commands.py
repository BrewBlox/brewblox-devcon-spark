"""
Tests brewblox_devcon_spark.commands
"""

import pytest
from brewblox_devcon_spark import commands

TESTED = commands.__name__


@pytest.fixture
def write_value_args():
    return dict(
        id=[127, 7],
        type=6,
        size=10,
        data=[0x0F]*10)


@pytest.fixture
def write_value_req(write_value_args):
    req = write_value_args.copy()
    req['opcode'] = 2
    return req


@pytest.fixture
def write_value_resp(write_value_args):
    return dict(
        errcode=commands.ErrorcodeEnum.OK,
        type=write_value_args['type'],
        size=write_value_args['size'],
        data=write_value_args['data']
    )


def test_known_commands():
    for cmd_name in [
        'READ_VALUE',
        'WRITE_VALUE',
        'CREATE_OBJECT',
        'DELETE_OBJECT',
        'LIST_OBJECTS',
        'FREE_SLOT',
        'CREATE_PROFILE',
        'DELETE_PROFILE',
        'ACTIVATE_PROFILE',
        'LOG_VALUES',
        'RESET',
        'FREE_SLOT_ROOT',
        'LIST_PROFILES',
        'READ_SYSTEM_VALUE',
        'WRITE_SYSTEM_VALUE',
    ]:
        command = commands.COMMAND_DEFS[cmd_name]
        assert command.opcode == cmd_name
        assert command.request
        assert command.response


def test_variable_id_length(write_value_args):

    command = commands.COMMAND_DEFS['WRITE_VALUE']
    bin_cmd = command.request.build(write_value_args)

    # nesting flag was added
    assert bin_cmd[1:3] == bytearray([0xFF, 0x07])

    # assert symmetrical encoding / decoding
    decoded = command.request.parse(bin_cmd)
    assert decoded.id == write_value_args['id']
    assert decoded.data == write_value_args['data']


def test_command_from_decoded(write_value_args):
    with pytest.raises(KeyError):
        commands.Command.from_decoded('spanish_inquisition', dict())

    cmd = commands.Command.from_decoded('write_value', write_value_args)

    assert cmd.encoded_request
    assert cmd.decoded_request == write_value_args

    assert cmd.encoded_response is None
    assert cmd.decoded_response is None


def test_command_from_encoded(write_value_args, write_value_resp, write_value_req):
    with pytest.raises(KeyError):
        commands.Command.from_encoded(commands.OpcodeEnum.build('UNUSED'), None)

    cmd_def = commands.COMMAND_DEFS['WRITE_VALUE']
    encoded_request = cmd_def.request.build(write_value_args)
    encoded_response = cmd_def.response.build(write_value_resp)

    cmd = commands.Command.from_encoded(encoded_request, encoded_response)

    assert cmd.encoded_request == encoded_request
    assert cmd.encoded_response == encoded_response

    assert dict(**cmd.decoded_request) == write_value_req
    assert cmd.decoded_response == write_value_resp


def test_command_props(write_value_args, write_value_resp, write_value_req):
    cmd_def = commands.COMMAND_DEFS['WRITE_VALUE']
    encoded_request = cmd_def.request.build(write_value_args)
    encoded_response = cmd_def.response.build(write_value_resp)

    # Request only
    for cmd in [
        commands.Command(
            cmd_def,
            encoded=(encoded_request, None)
        ),
        commands.Command(
            cmd_def,
            decoded=(write_value_req, None)
        )
    ]:
        assert cmd.encoded_request == encoded_request
        assert cmd.decoded_request == write_value_req
        assert cmd.encoded_response is None
        assert cmd.decoded_response is None

    # Response only
    for cmd in [
        commands.Command(
            cmd_def,
            encoded=(None, encoded_response)
        ),
        commands.Command(
            cmd_def,
            decoded=(None, write_value_resp)
        )
    ]:
        assert cmd.encoded_request is None
        assert cmd.decoded_request is None
        assert cmd.encoded_response == encoded_response
        assert cmd.decoded_response == write_value_resp
