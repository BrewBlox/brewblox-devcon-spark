"""
Tests brewblox_devcon_spark.commands
"""

import pytest
from brewblox_devcon_spark import commands

TESTED = commands.__name__


def test_known_commands():
    for cmd_name in [
        'CREATE_OBJECT',
        'CREATE_PROFILE',
        'ACTIVATE_PROFILE',
        'LIST_PROFILES',
        'LIST_OBJECTS',
        'READ_VALUE',
        'DELETE_OBJECT',
        'RESET',
    ]:
        command = commands.COMMANDS[cmd_name]
        assert command.opcode == cmd_name
        assert command.request
        assert command.response


def test_identify():
    byte_obj = commands.CBoxOpcodeEnum.build('LIST_OBJECTS')
    assert commands.identify(byte_obj).opcode == 'LIST_OBJECTS'

    with pytest.raises(KeyError):
        byte_obj = commands.CBoxOpcodeEnum.build('UNUSED')
        commands.identify(byte_obj)


def test_variable_id_length():
    id = [127, 7]
    args = dict(
        id=id,
        type='TEMPERATURE_SENSOR',
        reserved_size=10,
        data=[0x0F]*10)
    command = commands.COMMANDS['CREATE_OBJECT']
    bin_cmd = command.request.build(args)

    # nesting flag was added
    assert bin_cmd[1:3] == bytearray([0xFF, 0x07])

    # assert symmetrical encoding / decoding
    decoded = command.request.parse(bin_cmd)
    assert decoded.id == id
    assert decoded.data == args['data']
