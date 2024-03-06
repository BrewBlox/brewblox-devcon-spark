"""
Sequence block parser / serializer.

This converts Sequence block instructions from and to the line format.
"""

import re
from datetime import timedelta
from typing import Any, Iterable

from google.protobuf.descriptor import Descriptor, FieldDescriptor

from brewblox_devcon_spark.codec import bloxfield, time_utils
from brewblox_devcon_spark.codec.pb2 import Sequence_pb2, brewblox_pb2
from brewblox_devcon_spark.models import Block

INSTRUCTION_MSG_DESC: Descriptor = Sequence_pb2.Instruction.DESCRIPTOR
RAW_PREFIX = '__raw__'
VAR_PREFIX = '__var__'


def base_keys(keys: Iterable[str]) -> set[str]:
    return set(map(lambda k: k.removeprefix(RAW_PREFIX).removeprefix(VAR_PREFIX), keys))


def quoted(value: str) -> str:
    return f"'{value}'" if ' ' in value else value


def from_line(line: str, line_num: int) -> dict:
    """
    Converts Sequence line instruction to dict.

    Links in the output will only include the SID, not the NID.
    """
    if line.lstrip().startswith('#'):
        return {'COMMENT': {'text': line.strip()[1:]}}

    if ' ' in line:
        opcode, args = line.split(' ', 1)
    else:
        opcode = line
        args = ''

    try:
        # The generic `Instruction` is a big oneof in proto, with all opcodes mapped to fields
        # `fields_by_name[opcode]` yields the descriptor of a opcode field in the Instruction message
        #
        #     Message Instruction {
        #       oneof instruction_oneof {
        #         ...
        #         WaitDuration WAIT_DURATION = 4;  # <-- `opcode_field_desc` for opcode 'WAIT_DURATION'
        #         ...
        #       }
        #     }
        #
        opcode_field_desc: FieldDescriptor = INSTRUCTION_MSG_DESC.fields_by_name[opcode]

        # The descriptor for the specific instruction message
        #
        #     message WaitDuration {  # <-- `opcode_msg_desc` for opcode 'WAIT_DURATION'
        #       uint32 duration = 1
        #         [ (brewblox.field).unit = Second, (nanopb).int_size = IS_32 ];
        #     }
        opcode_msg_desc: Descriptor = opcode_field_desc.message_type

        # The fields in the specific instruction message
        # Here, the arguments for the specific instruction are declared
        #
        #     message WaitDuration {
        #       uint32 duration = 1  # <-- `opcode_arg_field_descs['duration']` for opcode 'WAIT_DURATION'
        #         [ (brewblox.field).unit = Second, (nanopb).int_size = IS_32 ];
        #     }
        opcode_arg_field_descs: dict[str, FieldDescriptor] = opcode_msg_desc.fields_by_name
    except KeyError:
        raise ValueError(f'line {line_num}: Invalid instruction name: `{opcode}`')

    def parse_arg_entry(key: str, value: str) -> tuple[str, Any]:
        raw_key = f'{RAW_PREFIX}{key}'
        var_key = f'{VAR_PREFIX}{key}'
        field_desc = opcode_arg_field_descs.get(raw_key)

        if '=' in value:
            raise ValueError(f'line {line_num}: Missing argument separator: `{key}={value}`')

        if not field_desc:
            raise ValueError(f'line {line_num}: Invalid argument name: `{key}`')

        if value.startswith('$'):
            return (var_key, value[1:])

        opts = field_desc.GetOptions().Extensions[brewblox_pb2.field]

        if opts.objtype:
            return (raw_key, {
                '__bloxtype': 'Link',
                'id': value,
            })

        elif opts.unit:
            unit_name = brewblox_pb2.UnitType.Name(opts.unit)
            value = value.strip()

            if unit_name in ['Celsius', 'DeltaCelsius']:
                # Decimal value followed by C / F / dC / dF
                # Unit notation is mandatory
                match = re.match(r'^(\d+\.?\d*)\s*(d?[CF])$', value)

                if not match:
                    raise ValueError(f'line {line_num}: Invalid temperature argument: `{key}={value}`')

                value = float(match[1])
                unit = match[2].replace('d', 'delta_').replace('C', 'degC').replace('F', 'degF')

                if ('Delta' in unit_name) != ('delta_' in unit):
                    raise ValueError(
                        f'line {line_num}: Mismatch between delta and absolute temperature: `{key}={value}{unit}`')

                return (raw_key, {
                    '__bloxtype': 'Quantity',
                    'value': value,
                    'unit': unit,
                })

            elif unit_name == 'Second':
                td = time_utils.parse_duration(value)

                return (raw_key, {
                    '__bloxtype': 'Quantity',
                    'value': int(td.total_seconds()),
                    'unit': 'second',
                })

            else:  # pragma: no cover
                raise NotImplementedError(f'{unit_name} quantities not yet implemented')

        else:
            try:
                return (raw_key, float(value))
            except ValueError:
                return (raw_key, value)

    # - the comma-separated argument string is split into `key=value` strings
    # - key and value are extracted from the `key=value` string
    # - spaces are stripped from both key and value
    # - quotes are stripped from value
    # - a {key:value} dict is constructed
    argdict = {argk.strip(): argv.strip().strip("'")
               for (argk, _, argv)
               in [arg.partition('=') for arg in args.split(',') if arg]}

    parsed = dict([parse_arg_entry(key, value)
                   for key, value in argdict.items()])

    # strip prefixes from fields - we need one per oneof, not all possible fields
    if missing := base_keys(opcode_arg_field_descs.keys()) - base_keys(parsed.keys()):
        raise ValueError(f'line {line_num}: Missing arguments: `{", ".join(missing)}`')

    return {opcode: parsed}


def to_line(args: dict) -> str:
    """
    Converts Sequence dict instruction to the line format.

    Link IDs must already have been converted to SID.
    """

    opcode, argdict = list(args.items())[0]
    opcode: str
    argdict: dict[str, Any]
    args: list[str] = []

    if opcode == 'COMMENT':
        text = argdict.get('text', '')
        return f'#{text}'

    if not argdict:
        return opcode

    for key, value in argdict.items():
        if key.startswith(VAR_PREFIX):
            key = key.removeprefix(VAR_PREFIX)
            value = quoted(f'${value}')

        else:
            key = key.removeprefix(RAW_PREFIX)

            if bloxfield.is_link(value):
                value = quoted(value['id'])

            elif bloxfield.is_quantity(value):
                amount = value['value']
                unit = value['unit']

                if 'deg' in unit:
                    unit = value['unit'].replace('delta_', 'd').replace('degC', 'C').replace('degF', 'F')
                    value = f'{round(amount, 2)}{unit}'

                elif unit == 'second':
                    value = time_utils.serialize_duration(timedelta(seconds=amount))

                else:  # pragma: no cover
                    raise NotImplementedError(f'{unit} quantities not yet implemented')

            elif isinstance(value, float):
                value = round(value, 2)

        args.append(f'{key}={value}')

    return ' '.join([opcode, ', '.join(args)])


def parse(block: Block):
    """
    Converts instructions in given Sequence block from line to dict format.
    """
    if 'instructions' in block.data:
        block.data['instructions'] = [from_line(s, idx + 1)
                                      for idx, s in enumerate(block.data['instructions'])]


def serialize(block: Block):
    """
    Converts instructions in given Sequence block from dict to line format.
    """
    if 'instructions' in block.data:
        block.data['instructions'] = [to_line(d)
                                      for d in block.data['instructions']]
