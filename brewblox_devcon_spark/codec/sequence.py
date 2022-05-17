"""
Sequence block parser / serializer.

This converts Sequence block instructions from and to the line format.
"""

import re

from brewblox_devcon_spark.codec import bloxfield
from brewblox_devcon_spark.codec.pb2 import Sequence_pb2, brewblox_pb2
from brewblox_devcon_spark.models import Block


def from_line(line: str, line_num: int) -> dict:
    if ' ' in line:
        opcode, args = line.split(' ', 1)
    else:
        opcode = line
        args = ''

    argdict = {argk.strip(): argv.strip().strip("'")
               for (argk, _, argv)
               in [arg.partition('=') for arg in args.split(',') if arg]}

    try:
        instruction_field = getattr(Sequence_pb2.Instruction, opcode)
    except AttributeError:
        raise ValueError(f'line {line_num}: Invalid instruction name: `{opcode}`')

    arg_fields_by_name = instruction_field.DESCRIPTOR.message_type.fields_by_name

    for key in argdict.keys():
        arg_field_desc = arg_fields_by_name.get(key)
        value = argdict[key]

        if '=' in value:
            raise ValueError(f'line {line_num}: Missing argument separator: `{key}={value}`')

        if not arg_field_desc:
            raise ValueError(f'line {line_num}: Invalid argument name: `{key}`')

        opts = arg_field_desc.GetOptions().Extensions[brewblox_pb2.field]

        if opts.objtype:
            argdict[key] = {
                '__bloxtype': 'Link',
                'id': value,
            }

        elif opts.unit:
            value = value.strip()

            # Decimal value followed by C / F / dC / dF
            # Unit notation is mandatory
            match = re.match(r'^(\d+\.?\d*)\s*(d?[CF])$', value)

            if not match:
                raise ValueError(f'line {line_num}: Invalid temperature argument: `{key}={value}`')

            value = float(match[1])
            unit = match[2].replace('d', 'delta_').replace('C', 'degC').replace('F', 'degF')

            argdict[key] = {
                '__bloxtype': 'Quantity',
                'value': value,
                'unit': unit,
            }

        else:
            try:
                argdict[key] = float(value)
            except ValueError:
                pass

    return {opcode: argdict}


def to_line(args: dict) -> str:
    opcode, argdict = list(args.items())[0]
    args: list[str] = []

    if not argdict:
        return opcode

    for key, value in argdict.items():
        if bloxfield.is_link(value):
            value = value['id']
            if ' ' in value:
                value = f"'{value}'"

        elif bloxfield.is_quantity(value):
            unit = value['unit'].replace('delta_', 'd').replace('degC', 'C').replace('degF', 'F')
            value = str(round(value['value'], 2)) + unit

        elif isinstance(value, float):
            value = round(value, 2)

        args.append(f'{key}={value}')

    return ' '.join([opcode, ', '.join(args)])


def parse(block: Block):
    block.data['instructions'] = [from_line(s, idx + 1)
                                  for idx, s in enumerate(block.data['instructions'])]


def serialize(block: Block):
    block.data['instructions'] = [to_line(d)
                                  for d in block.data['instructions']]
