"""
Tests brewblox_devcon_spark.commands
"""

import pytest
from construct import Struct

from brewblox_devcon_spark import commands, exceptions

TESTED = commands.__name__


@pytest.fixture
def object_args():
    return dict(
        object_nid=42,
        groups=[1],
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
    command = commands.ListObjectsCommand
    encoded = ','.join([
        '0000',
        '2a00''02''0600''0f0f0f0f0f0f0f0f0f0fd1',
        '2a00''02''0600''0f0f0f0f0f0f0f0f0f0fd1',
        '2a00''02''0600''0f0f0f0f0f0f0f0f0f0fd1',
    ])
    decoded = {
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
    assert isinstance(cmd.decoded_response, exceptions.CommandException)

    # Also without CRC
    cmd = commands.WriteObjectCommand.from_encoded(None, 'ff')
    assert isinstance(cmd.decoded_response, exceptions.CommandException)

    with pytest.raises(NotImplementedError):
        commands.DeleteObjectCommand.from_decoded(None, {'_errcode': -1})


def test_group_adapter():
    s = Struct('groups' / commands.GroupListAdapter())

    for left, right in [
        ([], b'\x00'),
        ([0, 1], b'\x03'),
        ([i for i in range(8)], b'\xFF')
    ]:
        assert s.build({'groups': left}) == right
        assert s.parse(right) == {'groups': left}

    with pytest.raises(ValueError):
        s.build({'groups': [8]})


def test_crc_failure():
    cmd = commands.WriteObjectCommand.from_encoded(None, '00F3')
    assert isinstance(cmd.decoded_response, exceptions.CRCFailed)

    cmd = commands.WriteObjectCommand.from_encoded('0A00')
    with pytest.raises(exceptions.CRCFailed):
        cmd.decoded_request


def test_too_many_args():
    cmd1 = commands.RebootCommand.from_args()
    cmd2 = commands.RebootCommand.from_args(unused_arg=True)
    assert len(cmd1.encoded_request) == len(cmd2.encoded_request)
