import pytest

from brewblox_devcon_spark import codec
from brewblox_devcon_spark.codec import sequence
from brewblox_devcon_spark.models import Block, DecodedPayload
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
