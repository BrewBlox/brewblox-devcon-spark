from base64 import b64decode, b64encode

import pytest

from brewblox_devcon_spark import codec
from brewblox_devcon_spark.codec import descriptors, lookup, sequence, unit_conversion
from brewblox_devcon_spark.codec.pb2 import Sequence_pb2
from brewblox_devcon_spark.models import Block, DecodedPayload, EncodedPayload, FirmwareDescription, ReadMode
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


def test_negative_temperatures():
    """to_line writes a sign, which from_line reads back"""
    line = sequence.to_line(
        {
            'SET_SETPOINT': {
                '__raw__target': {'__bloxtype': 'Link', 'id': 'setpoint'},
                '__raw__setting': {'__bloxtype': 'Quantity', 'value': -5.0, 'unit': 'degC'},
            },
        }
    )
    assert line == 'SET_SETPOINT target=setpoint, setting=-5.0C'
    assert sequence.from_line(line, 1)['SET_SETPOINT']['__raw__setting']['value'] == -5.0
    with pytest.raises(ValueError, match='Negative temperature difference'):
        sequence.from_line('WAIT_SETPOINT target=setpoint, precision=-1dC', 1)
    assert sequence.from_line('SET_SETPOINT target=setpoint, setting=-0.0F', 1)['SET_SETPOINT']['__raw__setting'] == {
        '__bloxtype': 'Quantity',
        'value': -0.0,
        'unit': 'degF',
    }


def _backup_sequence(lines: list[str]) -> Block:
    return Block(id='All closed', nid=102, type='Sequence', data={'enabled': True, 'instructions': lines})


def _firmware(proto_date: str) -> FirmwareDescription:
    return FirmwareDescription(
        firmware_version='1687e574',
        proto_version='94d21b71',
        firmware_date=proto_date,
        proto_date=proto_date,
    )


def test_complete_backup_lines():
    """Sequence lines in a backup are completed as the service that wrote them left them, by its proto date"""
    lines = [
        'SET_DIGITAL target=vA',
        'SET_DIGITAL target=vB, setting=1',
        'SET_DIGITAL target=vC',
        "WAIT_TEMP_BETWEEN target='Kettle Sensor', upper=$high",
        'WAIT_UNTIL time=None',
        '# comment, with a comma',
        'RESTART',
        'INVALID target=vA',
    ]

    # Services from the oneof arguments to the 2026-09 datetime change: both
    block = _backup_sequence(lines)
    note = sequence.complete_backup_lines(block, _firmware('2026-04-01'))
    assert block.data['instructions'] == [
        'SET_DIGITAL target=vA, setting=0',
        'SET_DIGITAL target=vB, setting=1',
        'SET_DIGITAL target=vC, setting=0',
        "WAIT_TEMP_BETWEEN target='Kettle Sensor', upper=$high, lower=0C",
        'WAIT_UNTIL time=0',
        '# comment, with a comma',
        'RESTART',
        'INVALID target=vA',
    ]
    assert note == (
        'Sequence `All closed` as an older service wrote it: '
        'added setting=0 on 2 lines, added lower=0C on 1 line, read time=None as time=0 on 1 line. '
        'These are the values the controller ran.'
    )
    for line in block.data['instructions'][:-1]:
        sequence.from_line(line, 1)

    # The first oneof proto, and the last one that wrote a zero datetime as None
    for proto_date in ['2024-03-01', '2026-09-24']:
        block = _backup_sequence(lines)
        sequence.complete_backup_lines(block, _firmware(proto_date))
        assert block.data['instructions'][:5] == [
            'SET_DIGITAL target=vA, setting=0',
            'SET_DIGITAL target=vB, setting=1',
            'SET_DIGITAL target=vC, setting=0',
            "WAIT_TEMP_BETWEEN target='Kettle Sensor', upper=$high, lower=0C",
            'WAIT_UNTIL time=0',
        ]

    # Up to proto 8434d4d4: unset arguments only
    block = _backup_sequence(lines)
    note = sequence.complete_backup_lines(block, _firmware('2026-10-11'))
    assert block.data['instructions'][4] == 'WAIT_UNTIL time=None'
    assert note.startswith('Sequence `All closed` as an older service wrote it: added setting=0 on 2 lines, ')

    # Before the oneof arguments, and backups without firmware, which are older: zero datetimes only
    for firmware in [_firmware('2024-02-26'), None]:
        block = _backup_sequence(lines)
        note = sequence.complete_backup_lines(block, firmware)
        assert block.data['instructions'][0] == 'SET_DIGITAL target=vA'
        assert block.data['instructions'][4] == 'WAIT_UNTIL time=0'
        assert note == (
            'Sequence `All closed` as an older service wrote it: read time=None as time=0 on 1 line. '
            'These are the values the controller ran.'
        )

    # Newer backups, complete lines, and no instructions: nothing changes
    for block, firmware in [
        (_backup_sequence(lines), _firmware('2026-10-12')),
        (_backup_sequence(['SET_DIGITAL target=vA, setting=0']), _firmware('2026-04-01')),
        (_backup_sequence([]), _firmware('2026-04-01')),
        (Block(id='All closed', nid=102, type='Sequence', data={'enabled': True}), _firmware('2026-04-01')),
    ]:
        before = block.model_copy(deep=True)
        assert sequence.complete_backup_lines(block, firmware) is None
        assert block == before


def test_complete_every_argument():
    """Each argument a backup line leaves out is added as text that from_line parses to its raw zero"""
    codec.setup()
    cdc = codec.CV.get()
    opcodes = [opcode for opcode in sequence.INSTRUCTION_MSG_DESC.fields if opcode.message_type.oneofs]
    lines = []
    for opcode in opcodes:
        line, changes = sequence._complete_line(opcode.name, unset=True, none_datetime=False)
        assert len(changes) == len(opcode.message_type.oneofs), line
        lines.append(line)

    for instruction in _written(cdc, lines).instructions.items:
        [(_, args)] = instruction.ListFields()
        for oneof in args.DESCRIPTOR.oneofs:
            assert args.WhichOneof(oneof.name) == f'__raw__{oneof.name}', instruction
            assert getattr(args, f'__raw__{oneof.name}') == 0, instruction
