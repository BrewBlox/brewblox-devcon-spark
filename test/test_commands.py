"""
Tests brewblox_devcon_spark.commands
"""

import pytest

from brewblox_devcon_spark import commands

TESTED = commands.__name__


@pytest.fixture
def write_value_args():
    return dict(
        object_id=42,
        object_type=6,
        object_data=bytes([0x0F]*10))


@pytest.fixture
def write_value_resp(write_value_args):
    return dict(
        object_id=write_value_args['object_id'],
        object_type=write_value_args['object_type'],
        object_data=write_value_args['object_data']
    )


def test_command_error():
    with pytest.raises(ValueError):
        commands.WriteValueCommand()


def test_command_from_decoded(write_value_args):
    cmd = commands.WriteValueCommand.from_decoded(write_value_args)

    assert cmd.encoded_request
    assert cmd.decoded_request == write_value_args

    assert cmd.encoded_response is None
    assert cmd.decoded_response is None


def test_command_from_encoded(write_value_args, write_value_resp):
    command = commands.WriteValueCommand
    decoded = command.from_decoded(write_value_args, write_value_resp)
    encoded = command.from_encoded(
        decoded.encoded_request,
        decoded.encoded_response
    )

    assert encoded.encoded_request == decoded.encoded_request
    assert encoded.encoded_response == decoded.encoded_response
    assert encoded.decoded_request == decoded.decoded_request
    assert encoded.decoded_response == decoded.decoded_response


def test_decode_nested():
    command = commands.ListProfilesCommand.from_encoded(None, '00ff00010203')
    assert command.decoded_response == {
        'profile_id': -1,
        'profiles': [0, 1, 2, 3]
    }


# def test_values():
#     command = NewListProfilesCommand
#     encoded = '00ff,00,01,02,03'
#     decoded = {
#         'profile_id': -1,
#         'profiles': [0, 1, 2, 3]
#     }

#     for cmd in [
#         command.from_encoded(None, encoded),
#         command.from_decoded(None, decoded)
#     ]:
#         assert cmd.encoded_request is None
#         assert cmd.decoded_request is None
#         assert cmd.encoded_response == encoded
#         assert cmd.decoded_response == decoded


def test_error():
    cmd = commands.WriteValueCommand.from_encoded(None, 'ff')
    assert isinstance(cmd.decoded_response, commands.CommandException)

    with pytest.raises(NotImplementedError):
        commands.DeleteObjectCommand.from_decoded(None, {'_errcode': -1})
