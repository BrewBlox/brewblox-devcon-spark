from base64 import b64decode, b64encode

import pytest

from brewblox_devcon_spark import codec
from brewblox_devcon_spark.codec import descriptors, lookup, sequence, unit_conversion
from brewblox_devcon_spark.codec.pb2 import Sequence_pb2
from brewblox_devcon_spark.models import Block, DecodedPayload, EncodedPayload, ReadMode
from brewblox_devcon_spark.spark_api import resolve_data_ids


def test_sequence_from_line():
    assert sequence.from_line('SET_SETPOINT target=Kettle Setpoint, setting=40C', 1) == {
        'SET_SETPOINT': {
            '__raw__target': {
                '__bloxtype': 'Link',
                'id': 'Kettle Setpoint',
            },
            '__raw__setting': {
                '__bloxtype': 'Quantity',
                'value': pytest.approx(40.0),
                'unit': 'degC',
            },
        },
    }

    assert sequence.from_line("SET_SETPOINT target='Kettle Setpoint   ', setting= 40 C ", 1) == {
        'SET_SETPOINT': {
            '__raw__target': {
                '__bloxtype': 'Link',
                'id': 'Kettle Setpoint   ',
            },
            '__raw__setting': {
                '__bloxtype': 'Quantity',
                'value': pytest.approx(40.0),
                'unit': 'degC',
            },
        },
    }

    assert sequence.from_line('WAIT_SETPOINT target=Kettle Setpoint, precision=1dC', 1) == {
        'WAIT_SETPOINT': {
            '__raw__target': {
                '__bloxtype': 'Link',
                'id': 'Kettle Setpoint',
            },
            '__raw__precision': {
                '__bloxtype': 'Quantity',
                'value': pytest.approx(1.0),
                'unit': 'delta_degC',
            },
        },
    }

    assert sequence.from_line('WAIT_DURATION duration=1m10s', 1) == {
        'WAIT_DURATION': {
            '__raw__duration': {
                '__bloxtype': 'Quantity',
                'value': 70,
                'unit': 'second',
            }
        }
    }

    assert sequence.from_line('SET_DIGITAL target=actuator, setting=STATE_ACTIVE', 1) == {
        'SET_DIGITAL': {
            '__raw__target': {
                '__bloxtype': 'Link',
                'id': 'actuator',
            },
            '__raw__setting': 'STATE_ACTIVE',
        }
    }

    assert sequence.from_line('SET_PWM target=actuator, setting=12.34', 1) == {
        'SET_PWM': {
            '__raw__target': {
                '__bloxtype': 'Link',
                'id': 'actuator',
            },
            '__raw__setting': pytest.approx(12.34),
        }
    }

    assert sequence.from_line('SET_SETPOINT target=Kettle Setpoint, setting=$kettle_setting', 1) == {
        'SET_SETPOINT': {
            '__raw__target': {
                '__bloxtype': 'Link',
                'id': 'Kettle Setpoint',
            },
            '__var__setting': 'kettle_setting',
        },
    }

    assert sequence.from_line("SET_SETPOINT target='$kettle_setpoint', setting= $kettle_setting ", 1) == {
        'SET_SETPOINT': {
            '__var__target': 'kettle_setpoint',
            '__var__setting': 'kettle_setting',
        },
    }

    assert sequence.from_line('   # Hello, this is "comment"    ', 1) == {
        'COMMENT': {'text': ' Hello, this is "comment"'},
    }

    assert sequence.from_line('# $not_a_variable', 1) == {
        'COMMENT': {'text': ' $not_a_variable'},
    }

    assert sequence.from_line('#', 1) == {
        'COMMENT': {'text': ''},
    }

    with pytest.raises(ValueError, match=r'line 1: Missing argument separator: `target=Kettle Setpoint setting=40C`'):
        sequence.from_line('SET_SETPOINT target=Kettle Setpoint setting=40C', 1)

    with pytest.raises(ValueError, match=r'line 1: Invalid instruction name: `set_setpoint`'):
        sequence.from_line('set_setpoint target=Kettle Setpoint, setting=40C', 1)

    with pytest.raises(ValueError, match=r'line 1: Invalid argument name: `magic`'):
        sequence.from_line('SET_SETPOINT magic=1', 1)

    with pytest.raises(ValueError, match=r'line 1: Invalid argument name: `magic`'):
        sequence.from_line('SET_SETPOINT magic=$var', 1)

    with pytest.raises(ValueError, match=r'line 1: Invalid argument name: `1s`'):
        sequence.from_line('WAIT_DURATION 1s', 1)

    with pytest.raises(ValueError, match=r'Invalid temperature'):
        sequence.from_line('WAIT_TEMP_ABOVE value=10m', 1)

    with pytest.raises(ValueError, match=r'Missing arguments'):
        sequence.from_line('SET_SETPOINT target=setpoint', 1)

    with pytest.raises(ValueError, match=r'Mismatch between delta and absolute'):
        sequence.from_line('WAIT_SETPOINT target=setpoint, precision=1C', 1)

    with pytest.raises(ValueError, match=r'Mismatch between delta and absolute'):
        sequence.from_line('SET_SETPOINT target=setpoint, setting=20dF', 1)


def test_sequence_to_line():
    assert (
        sequence.to_line(
            {
                'SET_SETPOINT': {
                    '__raw__target': {
                        '__bloxtype': 'Link',
                        'id': 'Kettle Setpoint   ',
                    },
                    '__raw__setting': {
                        '__bloxtype': 'Quantity',
                        'value': 40.0,
                        'unit': 'degC',
                    },
                },
            }
        )
        == "SET_SETPOINT target='Kettle Setpoint   ', setting=40.0C"
    )

    assert (
        sequence.to_line(
            {
                'WAIT_DURATION': {
                    '__raw__duration': {
                        '__bloxtype': 'Quantity',
                        'value': 70,
                        'unit': 'second',
                    }
                }
            }
        )
        == 'WAIT_DURATION duration=1m10s'
    )

    assert (
        sequence.to_line(
            {
                'SET_DIGITAL': {
                    '__raw__target': {
                        '__bloxtype': 'Link',
                        'id': 'actuator',
                    },
                    '__raw__setting': 'STATE_ACTIVE',
                }
            }
        )
        == 'SET_DIGITAL target=actuator, setting=STATE_ACTIVE'
    )

    assert (
        sequence.to_line(
            {
                'SET_PWM': {
                    '__raw__target': {
                        '__bloxtype': 'Link',
                        'id': 'actuator',
                    },
                    '__raw__setting': 23.4567,
                }
            }
        )
        == 'SET_PWM target=actuator, setting=23.46'
    )

    assert (
        sequence.to_line({'SET_PWM': {'__var__target': 'actuator', '__raw__setting': 23.4567}})
        == 'SET_PWM target=$actuator, setting=23.46'
    )

    assert (
        sequence.to_line({'SET_PWM': {'__var__target': 'actuator', '__var__setting': 'space setting'}})
        == "SET_PWM target=$actuator, setting='$space setting'"
    )

    # A zero datetime reads as None, and is written as 0
    assert sequence.to_line({'WAIT_UNTIL': {'__raw__time': None}}) == 'WAIT_UNTIL time=0'
    assert sequence.from_line('WAIT_UNTIL time=0', 1) == {'WAIT_UNTIL': {'__raw__time': 0}}

    assert (
        sequence.to_line(
            {
                'COMMENT': {'text': '    =)'},
            }
        )
        == '#    =)'
    )

    assert (
        sequence.to_line(
            {
                'COMMENT': {'text': '$not_a_variable'},
            }
        )
        == '#$not_a_variable'
    )

    assert (
        sequence.to_line(
            {
                'COMMENT': {},
            }
        )
        == '#'
    )


def test_no_args():
    assert sequence.from_line('RESTART', 1) == {'RESTART': {}}
    assert sequence.to_line({'RESTART': {}}) == 'RESTART'


def test_partial():
    # Logged blocks will not include instructions
    # User input may not include instructions
    block = Block(id='sequence', type='Sequence', data={})
    sequence.parse(block)
    assert not block.data
    sequence.serialize(block)
    assert not block.data

    # Null instructions are left to the codec: they clear the list
    block = Block(id='sequence', type='Sequence', data={'instructions': None})
    sequence.parse(block)
    assert block.data == {'instructions': None}


def test_codec_round_trip():
    # The instructions wrapper is flattened by the codec: sequence.py sees the bare list
    codec.setup()
    cdc = codec.CV.get()
    lines = [
        'ENABLE target=10',
        'WAIT_DURATION duration=1m10s',
        '# comment',
    ]
    block = Block(id='sequence', type='Sequence', data={'instructions': lines})
    sequence.parse(block)

    # spark_api resolves the link ids around the codec
    content = resolve_data_ids(block.data, int)
    payload = cdc.encode_payload(DecodedPayload(blockId=100, blockType='Sequence', content=content))
    decoded = cdc.decode_payload(payload)
    assert len(decoded.content['instructions']) == 3

    block = Block(id='sequence', type='Sequence', data=resolve_data_ids(decoded.content, str))
    sequence.serialize(block)
    assert block.data['instructions'] == [
        'ENABLE target=10',
        'WAIT_DURATION duration=1m10s',
        '# comment',
    ]


def test_unset_link_round_trip():
    """An unset link reads as None. to_line writes it as 0, which from_line parses back to link 0."""
    line = sequence.to_line(
        {
            'SET_SETPOINT': {
                '__raw__target': {'__bloxtype': 'Link', 'id': None},
                '__raw__setting': {'__bloxtype': 'Quantity', 'value': 20.0, 'unit': 'degC'},
            },
        }
    )
    assert line == 'SET_SETPOINT target=0, setting=20.0C'
    assert sequence.from_line(line, 1)['SET_SETPOINT']['__raw__target'] == {'__bloxtype': 'Link', 'id': '0'}


def test_zero_datetime_round_trip():
    """
    A zero datetime reads as None. to_line writes it as 0, which from_line parses back:
    a read line written back writes the same zero.
    """
    codec.setup()
    cdc = codec.CV.get()
    args = [
        (opcode.name, arg.name)
        for opcode in sequence.INSTRUCTION_MSG_DESC.fields
        for arg in opcode.message_type.fields
        if descriptors.options(arg).datetime
    ]
    assert args == [('WAIT_UNTIL', '__raw__time')]

    for opcode, arg in args:
        message = Sequence_pb2.Block()
        instruction = message.instructions.items.add()
        setattr(getattr(instruction, opcode), arg, 0)
        assert instruction.HasField(opcode)
        assert getattr(instruction, opcode).HasField(arg)

        payload = EncodedPayload(
            blockId=100,
            blockType=lookup.BlockType.Value('Sequence'),
            content=b64encode(message.SerializeToString()).decode(),
        )
        decoded = cdc.decode_payload(payload)
        assert decoded.content['instructions'] == [{opcode: {arg: None}}]

        block = Block(id='sequence', type='Sequence', data=resolve_data_ids(decoded.content, str))
        sequence.serialize(block)
        assert block.data['instructions'] == [f'{opcode} {arg.removeprefix(sequence.RAW_PREFIX)}=0']

        sequence.parse(block)
        content = resolve_data_ids({'instructions': block.data['instructions']}, int)
        payload = cdc.encode_payload(DecodedPayload(blockId=100, blockType='Sequence', content=content))
        written = Sequence_pb2.Block.FromString(b64decode(payload.content))
        assert written.instructions == message.instructions


def _read_lines(cdc: codec.Codec, message: Sequence_pb2.Block) -> list[str]:
    payload = EncodedPayload(
        blockId=100,
        blockType=lookup.BlockType.Value('Sequence'),
        content=b64encode(message.SerializeToString()).decode(),
    )
    block = Block(id='sequence', type='Sequence', data=resolve_data_ids(cdc.decode_payload(payload).content, str))
    sequence.serialize(block)
    return block.data['instructions']


def _written(cdc: codec.Codec, lines: list[str]) -> Sequence_pb2.Block:
    block = Block(id='sequence', type='Sequence', data={'instructions': lines})
    sequence.parse(block)
    content = resolve_data_ids(block.data, int)
    payload = cdc.encode_payload(DecodedPayload(blockId=100, blockType='Sequence', content=content))
    return Sequence_pb2.Block.FromString(b64decode(payload.content))


def test_unset_arguments():
    """
    An instruction last written before the arguments became oneofs holds no member for a zero argument.
    The controller runs it as the raw zero: it reads as that value, and writing it back stores the member.
    """
    codec.setup()
    cdc = codec.CV.get()

    # Every argument of every opcode
    message = Sequence_pb2.Block()
    for opcode in sequence.INSTRUCTION_MSG_DESC.fields:
        if opcode.message_type.oneofs:
            getattr(message.instructions.items.add(), opcode.name).SetInParent()
    lines = _read_lines(cdc, message)
    assert len(lines) == 21
    for line in [
        'ENABLE target=0',
        'WAIT_DURATION duration=0s',
        'WAIT_UNTIL time=0',
        'WAIT_TEMP_BETWEEN target=0, lower=0.0C, upper=0.0C',
        'WAIT_SETPOINT target=0, precision=0.0dC',
        'SET_DIGITAL target=0, setting=STATE_INACTIVE',
        'SET_PWM target=0, setting=0.0',
    ]:
        assert line in lines

    written = _written(cdc, lines)
    for instruction in written.instructions.items:
        [(_, args)] = instruction.ListFields()
        assert all(args.WhichOneof(oneof.name) for oneof in args.DESCRIPTOR.oneofs), instruction

    # A member that is set is kept. A zero temperature is 0 °C, in the user's unit.
    message = Sequence_pb2.Block()
    setattr(message.instructions.items.add().SET_DIGITAL, '__raw__target', 5)
    setattr(message.instructions.items.add().SET_SETPOINT, '__raw__target', 6)
    unit_conversion.CV.get().temperature = 'degF'
    try:
        lines = _read_lines(cdc, message)
    finally:
        unit_conversion.CV.get().temperature = 'degC'
    assert lines == [
        'SET_DIGITAL target=5, setting=STATE_INACTIVE',
        'SET_SETPOINT target=6, setting=32.0F',
    ]
    setting = _written(cdc, lines).instructions.items[0].SET_DIGITAL
    assert setting.WhichOneof('setting') == '__raw__setting'
    assert getattr(setting, '__raw__setting') == 0

    # A block without instructions, as in a CHANGED read
    payload = EncodedPayload(
        blockId=100,
        blockType=lookup.BlockType.Value('Sequence'),
        content=b64encode(Sequence_pb2.Block(enabled=True).SerializeToString()).decode(),
    )
    assert 'instructions' not in cdc.decode_payload(payload, mode=ReadMode.CHANGED).content
    assert cdc.decode_payload(payload).content['instructions'] == []
