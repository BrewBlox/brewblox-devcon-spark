"""
Tests brewblox_devcon_spark.commands
"""

from brewblox_devcon_spark import commands
from binascii import unhexlify

TESTED = commands.__name__


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


def test_variable_id_length():
    id = [127, 7]
    args = dict(
        id=id,
        type=6,
        size=10,
        data=[0x0F]*10)
    command = commands.COMMAND_DEFS['WRITE_VALUE']
    bin_cmd = command.request.build(args)

    # nesting flag was added
    assert bin_cmd[1:3] == bytearray([0xFF, 0x07])

    # assert symmetrical encoding / decoding
    decoded = command.request.parse(bin_cmd)
    assert decoded.id == id
    assert decoded.data == args['data']


def test_response_converter():
    request, response = unhexlify('05'), unhexlify('81')
    converter = commands.ResponseConverter(request, response)

    assert isinstance(converter.error, commands.CommandException)
    assert converter.response is None
