"""
Sequence block parser / serializer.

This converts Sequence block instructions from and to the line format.
"""

import re
from datetime import timedelta
from typing import Any

from brewblox_devcon_spark.codec import bloxfield, time_utils
from brewblox_devcon_spark.codec.pb2 import Sequence_pb2, brewblox_pb2
from brewblox_devcon_spark.models import Block


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
        instruction_field = getattr(Sequence_pb2.Instruction, opcode)
        arg_fields_by_name = instruction_field.DESCRIPTOR.message_type.fields_by_name
    except AttributeError:
        raise ValueError(f'line {line_num}: Invalid instruction name: `{opcode}`')

    def parse_arg_value(key: str, value: str) -> Any:
        field_desc = arg_fields_by_name.get(key)

        if '=' in value:
            raise ValueError(f'line {line_num}: Missing argument separator: `{key}={value}`')

        if not field_desc:
            raise ValueError(f'line {line_num}: Invalid argument name: `{key}`')

        opts = field_desc.GetOptions().Extensions[brewblox_pb2.field]

        if opts.objtype:
            return {
                '__bloxtype': 'Link',
                'id': value,
            }

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

                return {
                    '__bloxtype': 'Quantity',
                    'value': value,
                    'unit': unit,
                }

            elif unit_name == 'Second':
                td = time_utils.parse_duration(value)

                return {
                    '__bloxtype': 'Quantity',
                    'value': int(td.total_seconds()),
                    'unit': 'second',
                }

            else:  # pragma: no cover
                raise NotImplementedError(f'{unit_name} quantities not yet implemented')

        else:
            try:
                return float(value)
            except ValueError:
                return value

    # - the comma-separated argument string is split into `key=value` strings
    # - key and value are extracted from the `key=value` string
    # - spaces are stripped from both key and value
    # - quotes are stripped from value
    # - a {key:value} dict is constructed
    argdict = {argk.strip(): argv.strip().strip("'")
               for (argk, _, argv)
               in [arg.partition('=') for arg in args.split(',') if arg]}

    parsed = {
        key: parse_arg_value(key, value)
        for key, value in argdict.items()
    }

    if missing := set(arg_fields_by_name.keys()) - set(parsed.keys()):
        raise ValueError(f'line {line_num}: Missing arguments: `{", ".join(missing)}`')

    return {opcode: parsed}


def to_line(args: dict) -> str:
    """
    Converts Sequence dict instruction to the line format.

    Link IDs must already have been converted to SID.
    """

    opcode, argdict = list(args.items())[0]
    args: list[str] = []

    if opcode == 'COMMENT':
        text = argdict.get('text', '')
        return f'#{text}'

    if not argdict:
        return opcode

    for key, value in argdict.items():
        if bloxfield.is_link(value):
            value = value['id']
            if ' ' in value:
                value = f"'{value}'"

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
