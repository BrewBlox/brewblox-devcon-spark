"""
Tests brewblox_devcon_spark.commands
"""

import pytest
from construct import Struct

from brewblox_devcon_spark import commands

TESTED = commands.__name__


@pytest.fixture
def object_args():
    return dict(
        object_id=42,
        profiles=[1],
        object_type=6,
        object_data=bytes([0x0F]*10))


def test_command_error():
    with pytest.raises(ValueError):
        commands.ReadObjectCommand()


def test_command_from_decoded(object_args):
    cmd = commands.WriteObjectCommand.from_decoded(object_args)

    assert cmd.encoded_request
    assert cmd.decoded_request == object_args

    assert cmd.encoded_response is None
    assert cmd.decoded_response is None


def test_command_from_encoded(object_args):
    command = commands.WriteObjectCommand
    decoded = command.from_decoded(object_args, object_args)
    encoded = command.from_encoded(
        decoded.encoded_request,
        decoded.encoded_response
    )

    assert encoded.encoded_request == decoded.encoded_request
    assert encoded.encoded_response == decoded.encoded_response
    assert encoded.decoded_request == decoded.decoded_request
    assert encoded.decoded_response == decoded.decoded_response


def test_values(object_args):
    command = commands.ListActiveObjectsCommand
    encoded = ','.join([
        '000e2a',
        '002a0200060f0f0f0f0f0f0f0f0f0f55',
        '002a0200060f0f0f0f0f0f0f0f0f0f55',
        '002a0200060f0f0f0f0f0f0f0f0f0f55',
    ])
    decoded = {
        'profiles': [1, 2, 3],
        'objects': [object_args]*3
    }

    for cmd in [
        command.from_encoded(None, encoded),
        command.from_decoded(None, decoded)
    ]:
        assert cmd.encoded_request is None
        assert cmd.decoded_request is None
        assert cmd.encoded_response == encoded
        assert cmd.decoded_response == decoded


def test_error():
    cmd = commands.WriteObjectCommand.from_encoded(None, 'fff3')
    assert isinstance(cmd.decoded_response, commands.CommandException)

    # Also without CRC
    cmd = commands.WriteObjectCommand.from_encoded(None, 'ff')
    assert isinstance(cmd.decoded_response, commands.CommandException)

    with pytest.raises(NotImplementedError):
        commands.DeleteObjectCommand.from_decoded(None, {'_errcode': -1})


def test_profile_adapter():
    s = Struct('profiles' / commands.ProfileListAdapter())

    for left, right in [
        ([], b'\x00'),
        ([0, 1], b'\x03'),
        ([i for i in range(8)], b'\xFF')
    ]:
        assert s.build({'profiles': left}) == right
        assert s.parse(right) == {'profiles': left}

    with pytest.raises(ValueError):
        s.build({'profiles': [8]})


def test_crc_failure():
    cmd = commands.WriteObjectCommand.from_encoded(None, '00F3')
    assert isinstance(cmd.decoded_response, commands.CRCFailure)

    cmd = commands.WriteObjectCommand.from_encoded('0A00')
    with pytest.raises(commands.CRCFailure):
        cmd.decoded_request
