"""
Tests brewblox_devcon_spark.commands
"""

import pytest
from brewblox_devcon_spark import commands

TESTED = commands.__name__


@pytest.fixture
def write_value_args():
    return dict(
        object_id=[127, 7],
        object_type=6,
        object_data=bytes([0x0F]*10))


@pytest.fixture
def write_value_req(write_value_args):
    req = write_value_args.copy()
    req['opcode'] = 2
    return req


@pytest.fixture
def write_value_resp(write_value_args):
    return dict(
        errcode=commands.ErrorcodeEnum.OK,
        object_id=write_value_args['object_id'],
        object_type=write_value_args['object_type'],
        object_data=write_value_args['object_data']
    )


def test_variable_id_length(write_value_args):

    command = commands.WriteValueCommand().from_args(**write_value_args)
    bin_cmd = command.encoded_request

    # nesting flag was added
    assert bin_cmd[1:3] == bytearray([0xFF, 0x07])

    # assert symmetrical encoding / decoding
    decoded = command.request.parse(bin_cmd)
    assert decoded.object_id == write_value_args['object_id']
    assert decoded.object_data == write_value_args['object_data']


def test_command_from_decoded(write_value_args):
    cmd = commands.WriteValueCommand().from_decoded(write_value_args)

    assert cmd.encoded_request
    assert cmd.decoded_request == write_value_args

    assert cmd.encoded_response is None
    assert cmd.decoded_response is None


def test_command_from_encoded(write_value_args, write_value_resp, write_value_req):
    builder = commands.WriteValueCommand()
    encoded_request = builder.request.build(write_value_args)
    encoded_response = builder.response.build(write_value_resp)

    cmd = commands.WriteValueCommand().from_encoded(encoded_request, encoded_response)

    assert cmd.encoded_request == encoded_request
    assert cmd.encoded_response == encoded_response

    assert cmd.decoded_request == write_value_req
    assert cmd.decoded_response == write_value_resp


def test_command_props(write_value_args, write_value_resp, write_value_req):
    command = commands.WriteValueCommand()
    encoded_request = command.request.build(write_value_args)
    encoded_response = command.response.build(write_value_resp)

    # Request only
    for cmd in [
        command.from_encoded(request=encoded_request),
        command.from_decoded(request=write_value_req),
    ]:
        assert cmd.encoded_request == encoded_request
        assert cmd.decoded_request == write_value_req
        assert cmd.encoded_response is None
        assert cmd.decoded_response is None

    # Response only
    for cmd in [
        command.from_encoded(response=encoded_response),
        command.from_decoded(response=write_value_resp),
    ]:
        assert cmd.encoded_request is None
        assert cmd.decoded_request is None
        assert cmd.encoded_response == encoded_response
        assert cmd.decoded_response == write_value_resp


def test_pretty_raw():
    command = commands.WriteValueCommand()

    assert command._pretty_raw(bytes([0xde, 0xad])) == b'dead'
    assert command._pretty_raw(None) is None
