"""
Sequence block parser / serializer.

This converts Sequence block instructions from and to the line format.
"""

import re
from collections import Counter
from collections.abc import Iterable
from datetime import timedelta
from typing import Any

from google.protobuf.descriptor import Descriptor, FieldDescriptor
from google.protobuf.message import Message

from brewblox_devcon_spark.codec import bloxfield, time_utils
from brewblox_devcon_spark.codec.pb2 import Sequence_pb2, brewblox_pb2
from brewblox_devcon_spark.models import Block, FirmwareDescription

INSTRUCTION_MSG_DESC: Descriptor = Sequence_pb2.Instruction.DESCRIPTOR
RAW_PREFIX = '__raw__'
VAR_PREFIX = '__var__'

# What older services wrote into the Sequence lines of a backup, by the proto date the backup records:
# the date in firmware.ini, as the controller's handshake reports it.
ONEOF_ARGUMENTS_FROM = '2024-03-01'
"""
Proto a5dc48c8 made every instruction argument a raw/var oneof.
Before it, a backup line carried every argument, zeros included.
"""
UNSET_ARGUMENTS_TO = '2026-10-11'
"""
Proto 8434d4d4. Services up to it left out an argument the controller held no member for (see `fill_unset_arguments`).
The service that fills them in pins this proto too: its backups have nothing to complete.
"""
NONE_DATETIME_TO = '2026-09-24'
"""Protos 5bab8b2d and c1f698c5. Services until the second wrote a zero datetime as `None`."""


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
            return (
                raw_key,
                {
                    '__bloxtype': 'Link',
                    'id': value,
                },
            )

        if opts.unit:
            unit_name = brewblox_pb2.UnitType.Name(opts.unit)
            value = value.strip()

            if unit_name in ['Celsius', 'DeltaCelsius']:
                # Decimal value followed by C / F / dC / dF
                # Unit notation is mandatory
                match = re.match(r'^(-?\d+\.?\d*)\s*(d?[CF])$', value)

                if not match:
                    raise ValueError(f'line {line_num}: Invalid temperature argument: `{key}={value}`')

                value = float(match[1])
                unit = match[2].replace('d', 'delta_').replace('C', 'degC').replace('F', 'degF')

                if ('Delta' in unit_name) != ('delta_' in unit):
                    raise ValueError(
                        f'line {line_num}: Mismatch between delta and absolute temperature: `{key}={value}{unit}`'
                    )

                return (
                    raw_key,
                    {
                        '__bloxtype': 'Quantity',
                        'value': value,
                        'unit': unit,
                    },
                )

            if unit_name == 'Second':
                td = time_utils.parse_duration(value)

                return (
                    raw_key,
                    {
                        '__bloxtype': 'Quantity',
                        'value': int(td.total_seconds()),
                        'unit': 'second',
                    },
                )

            # pragma: no cover
            raise NotImplementedError(f'{unit_name} quantities not yet implemented')

        try:
            return (raw_key, float(value))
        except ValueError:
            return (raw_key, value)

    # - the comma-separated argument string is split into `key=value` strings
    # - key and value are extracted from the `key=value` string
    # - spaces are stripped from both key and value
    # - quotes are stripped from value
    # - a {key:value} dict is constructed
    argdict = {
        argk.strip(): argv.strip().strip("'")
        for (argk, _, argv) in [arg.partition('=') for arg in args.split(',') if arg]
    }

    parsed = dict([parse_arg_entry(key, value) for key, value in argdict.items()])

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
                # An unset link reads as None: 0 parses back to the same link
                value = quoted(value['id'] if value['id'] is not None else '0')

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

            # A zero datetime reads as None: 0 parses back to the same value
            elif value is None:
                value = 0

        args.append(f'{key}={value}')

    return ' '.join([opcode, ', '.join(args)])


def parse(block: Block):
    """
    Converts instructions in given Sequence block from line to dict format.
    Null instructions are left to the codec: they clear the list.
    """
    if block.data.get('instructions') is not None:
        block.data['instructions'] = [from_line(s, idx + 1) for idx, s in enumerate(block.data['instructions'])]


def serialize(block: Block):
    """
    Converts instructions in given Sequence block from dict to line format.
    """
    if 'instructions' in block.data:
        block.data['instructions'] = [to_line(d) for d in block.data['instructions']]


def fill_unset_arguments(message: Message):
    """
    Sets every instruction argument the block holds no member for to its raw zero, in place.

    Before the arguments became raw/var oneofs (proto a5dc48c8, 2024-03), they were plain proto3 fields,
    which leave a zero off the wire. The oneof members kept the field numbers, so an instruction
    last written before then holds no member for a zero argument, on every firmware since.
    The controller runs it as the raw zero. Filled in, it reads as that value,
    and writing the instruction back stores it explicitly.
    """
    if not message.HasField('instructions'):
        return

    for instruction in message.instructions.items:
        for _, args in instruction.ListFields():
            for oneof in args.DESCRIPTOR.oneofs:
                if args.WhichOneof(oneof.name) is None:
                    setattr(args, f'{RAW_PREFIX}{oneof.name}', 0)


def _zero_text(field_desc: FieldDescriptor) -> str:
    """The line text that from_line() parses to the raw zero of an argument"""
    opts = field_desc.GetOptions().Extensions[brewblox_pb2.field]
    unit_name = brewblox_pb2.UnitType.Name(opts.unit)
    return {'Celsius': '0C', 'DeltaCelsius': '0dC', 'Second': '0s'}.get(unit_name, '0')


def _complete_line(line: str, *, unset: bool, none_datetime: bool) -> tuple[str, list[str]]:
    """
    Completes a line as an older service wrote it.
    `unset` adds every argument the line leaves out as its raw zero.
    `none_datetime` reads a datetime written as `None` as 0.
    Returns the line and a description of each change.
    Lines that from_line() refuses for other reasons are left to it.
    """
    opcode, _, args = line.partition(' ')
    opcode_field_desc = INSTRUCTION_MSG_DESC.fields_by_name.get(opcode)
    if line.lstrip().startswith('#') or opcode_field_desc is None:
        return line, []

    arg_descs = opcode_field_desc.message_type.fields_by_name
    entries: list[str] = []
    changes: list[str] = []

    for key, sep, value in [arg.partition('=') for arg in args.split(',') if arg]:
        key, value = key.strip(), value.strip()
        field_desc = arg_descs.get(f'{RAW_PREFIX}{key}')
        datetime = field_desc and field_desc.GetOptions().Extensions[brewblox_pb2.field].datetime
        if none_datetime and datetime and value == 'None':
            value = '0'
            changes.append(f'read {key}=None as {key}=0')
        entries.append(f'{key}{sep}{value}')

    if unset:
        given = base_keys(entry.partition('=')[0] for entry in entries)
        for oneof in opcode_field_desc.message_type.oneofs:
            if oneof.name not in given:
                entry = f'{oneof.name}={_zero_text(arg_descs[f"{RAW_PREFIX}{oneof.name}"])}'
                entries.append(entry)
                changes.append(f'added {entry}')

    if not changes:
        return line, []

    return ' '.join([opcode, ', '.join(entries)]), changes


def complete_backup_lines(block: Block, firmware: FirmwareDescription | None) -> str | None:
    """
    Completes the lines of a Sequence in a backup as the service that wrote the backup left them, in place.
    Only for backup loads: a line a user leaves an argument out of is still refused.

    `firmware` is the one the backup records, by the proto date of which the completions are chosen:
    - Services from proto a5dc48c8 to 8434d4d4 left out an argument the controller held no member for.
      It is added as the raw zero the controller ran.
    - Services until proto c1f698c5 wrote a zero datetime as `None`. It is read as 0.
      A backup without firmware is older than both.

    Returns a description of the changes for the import messages, or None if nothing changed.
    """
    lines = block.data.get('instructions')
    proto_date = firmware.proto_date if firmware else ''
    unset = ONEOF_ARGUMENTS_FROM <= proto_date <= UNSET_ARGUMENTS_TO
    none_datetime = proto_date <= NONE_DATETIME_TO

    if not lines:
        return None

    completed = [_complete_line(line, unset=unset, none_datetime=none_datetime) for line in lines]
    counts = Counter(change for _, changes in completed for change in changes)
    if not counts:
        return None

    block.data['instructions'] = [line for line, _ in completed]
    done = ', '.join(f'{change} on {n} {"line" if n == 1 else "lines"}' for change, n in counts.items())
    return f'Sequence `{block.id}` as an older service wrote it: {done}. These are the values the controller ran.'
