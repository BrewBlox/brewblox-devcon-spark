import pytest

from brewblox_devcon_spark.codec import sequence
from brewblox_devcon_spark.models import Block


def test_sequence_from_line():
    assert sequence.from_line(
        'SET_SETPOINT target=Kettle Setpoint, setting=40C',
        1
    ) == {
        'SET_SETPOINT': {
            'target': {
                '__bloxtype': 'Link',
                'id': 'Kettle Setpoint',
            },
            'setting': {
                '__bloxtype': 'Quantity',
                'value': pytest.approx(40.0),
                'unit': 'degC',
            },
        },
    }

    assert sequence.from_line(
        "SET_SETPOINT target='Kettle Setpoint   ', setting= 40 C ",
        1
    ) == {
        'SET_SETPOINT': {
            'target': {
                '__bloxtype': 'Link',
                'id': 'Kettle Setpoint   ',
            },
            'setting': {
                '__bloxtype': 'Quantity',
                'value': pytest.approx(40.0),
                'unit': 'degC',
            },
        },
    }

    assert sequence.from_line(
        'WAIT_SETPOINT target=Kettle Setpoint, precision=1dC',
        1
    ) == {
        'WAIT_SETPOINT': {
            'target': {
                '__bloxtype': 'Link',
                'id': 'Kettle Setpoint',
            },
            'precision': {
                '__bloxtype': 'Quantity',
                'value': pytest.approx(1.0),
                'unit': 'delta_degC',
            },
        },
    }

    assert sequence.from_line(
        'WAIT_DURATION duration=1m10s',
        1
    ) == {
        'WAIT_DURATION': {
            'duration': {
                '__bloxtype': 'Quantity',
                'value': 70,
                'unit': 'second',
            }
        }
    }

    assert sequence.from_line(
        'SET_DIGITAL target=actuator, setting=STATE_ACTIVE',
        1
    ) == {
        'SET_DIGITAL': {
            'target': {
                '__bloxtype': 'Link',
                'id': 'actuator',
            },
            'setting': 'STATE_ACTIVE'
        }
    }

    assert sequence.from_line(
        'SET_PWM target=actuator, setting=12.34',
        1
    ) == {
        'SET_PWM': {
            'target': {
                '__bloxtype': 'Link',
                'id': 'actuator',
            },
            'setting': pytest.approx(12.34)
        }
    }

    assert sequence.from_line(
        '   # Hello, this is "comment"    ',
        1
    ) == {
        'COMMENT': {'text': ' Hello, this is "comment"'},
    }

    assert sequence.from_line(
        '#',
        1
    ) == {
        'COMMENT': {'text': ''},
    }

    with pytest.raises(ValueError, match=r'line 1: Missing argument separator: `target=Kettle Setpoint setting=40C`'):
        sequence.from_line('SET_SETPOINT target=Kettle Setpoint setting=40C', 1)

    with pytest.raises(ValueError, match=r'line 1: Invalid instruction name: `set_setpoint`'):
        sequence.from_line('set_setpoint target=Kettle Setpoint, setting=40C', 1)

    with pytest.raises(ValueError, match=r'line 1: Invalid argument name: `magic`'):
        sequence.from_line('SET_SETPOINT magic=1', 1)

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

    assert sequence.to_line({
        'SET_SETPOINT': {
            'target': {
                '__bloxtype': 'Link',
                'id': 'Kettle Setpoint   ',
            },
            'setting': {
                '__bloxtype': 'Quantity',
                'value': 40.0,
                'unit': 'degC',
            },
        },
    }) == "SET_SETPOINT target='Kettle Setpoint   ', setting=40.0C"

    assert sequence.to_line({
        'WAIT_DURATION': {
            'duration': {
                '__bloxtype': 'Quantity',
                'value': 70,
                'unit': 'second',
            }
        }
    }) == 'WAIT_DURATION duration=1m10s'

    assert sequence.to_line({
        'SET_DIGITAL': {
            'target': {
                '__bloxtype': 'Link',
                'id': 'actuator',
            },
            'setting': 'STATE_ACTIVE'
        }
    }) == 'SET_DIGITAL target=actuator, setting=STATE_ACTIVE'

    assert sequence.to_line({
        'SET_PWM': {
            'target': {
                '__bloxtype': 'Link',
                'id': 'actuator',
            },
            'setting': 23.4567
        }
    }) == 'SET_PWM target=actuator, setting=23.46'

    assert sequence.to_line({
        'COMMENT': {'text': '    =)'},
    }) == '#    =)'

    assert sequence.to_line({
        'COMMENT': {},
    }) == '#'


def test_partial():
    # Logged blocks will not include instructions
    # User input may not include instructions
    block = Block(id='sequence', type='Sequence', data={})
    sequence.parse(block)
    assert not block.data
    sequence.serialize(block)
    assert not block.data
