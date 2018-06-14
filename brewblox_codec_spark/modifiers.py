"""
Input/output modification functions for transcoding
"""

import glob
import logging
from base64 import b64decode, b64encode
from binascii import hexlify, unhexlify
from typing import Any, Callable, List, Tuple, Optional

import dpath
from brewblox_codec_spark.proto import brewblox_pb2
from google.protobuf import json_format
from google.protobuf.descriptor import DescriptorBase, FieldDescriptor
from google.protobuf.message import Message
from pint import UnitRegistry

LOGGER = logging.getLogger(__name__)

# Creating the unit registry involves reading settings from file
# This only has to be done once per application start
_UREG = UnitRegistry()
Quantity = _UREG.Quantity


BREWBLOX_PROVIDER = brewblox_pb2.brewblox
UNIT_START_CHAR = '['
UNIT_END_CHAR = ']'
DESC_CACHE = {}


def modify_if_present(obj: dict, path: str, func: Callable) -> dict:
    """
    Replaces a value in a (possibly nested) dict.

    If path is invalid, no values are changed.

    Example:
        >>> input = {'nested': { 'collection': { 'value': 0 }}}
        >>> output = modify_if_present(
                        obj=input,
                        path='nested/collection/value',
                        func=lambda v: v +1
                    )
        >>> print(output)
        {'nested': { 'collection': { 'value': 1 }}}
        >>> print(input)
        {'nested': { 'collection': { 'value': 1 }}}

    """
    for key, val in dpath.util.search(obj, path, yielded=True):
        dpath.util.set(obj, key, func(val))

    return obj


def _get_field(msg: Message, path: str):
    """
    Returns the nested Protobuf field associated with the message and path string.
    """
    descriptor = msg.DESCRIPTOR
    path_list = path = [s for s in path.split('/') if s]  # drops empty sections

    for p in path_list[:-1]:
        descriptor = descriptor.fields_by_name[p].message_type

    leaf = path_list[-1]
    field = descriptor.fields_by_name[leaf]
    return field


def _find_option_fields(desc: DescriptorBase, path=''):
    if desc.has_options:
        yield desc, _field_options(desc), path

    if isinstance(desc, FieldDescriptor):
        message = desc.message_type
    else:
        message = desc

    if message:
        for field_name in message.fields_by_name:
            field_desc = message.fields_by_name[field_name]
            field_path = f'{path}/{field_name}'
            yield from _find_option_fields(field_desc, field_path)

    raise StopIteration()


def _cached_option_fields(desc: DescriptorBase):
    if desc not in DESC_CACHE:
        DESC_CACHE[desc] = [t for t in _find_option_fields(desc)]

    yield from DESC_CACHE[desc]


def _field_options(
    field: FieldDescriptor,
    provider: FieldDescriptor=BREWBLOX_PROVIDER
):
    return field.GetOptions().Extensions[provider]


def _apply_changes(obj: dict, changes: List[Tuple[str, Optional[str], Any]]):
    for (path, new_path, val) in changes:
        if new_path:
            dpath.util.delete(obj, glob.escape(path))
            dpath.util.new(obj, new_path, val)
        else:
            dpath.util.set(obj, path, val)

    return obj


def encode_quantity(message: Message, obj: dict) -> dict:
    """
    Converts input values with a post-fixed unit notation to controller values.
    Controller units are determined by Protobuf options.

    Example:
        >>> values = {
            'settings': {
                'address': 'FF',
                'offset[delta_degF]': 20
            }
        }

        >>> encode_quantity(
            OneWireTempSensor_pb2.OneWireTempSensor,
            values
        )

        # From OneWireTempSensor.proto:
        #
        # message OneWireTempSensor {
        #   message Settings {
        #     bytes address = 1;
        #     sint32 offset = 2 [(brewblox).unit = "delta_degC", (brewblox).scale = 256];
        #   }
        # ...

        >>> print(values)
        {
            'settings': {
                'address': 'FF',  # No unit notation -> not converted
                'offset': 2844    # Converted to delta_degC, scaled * 256, and rounded to int
            }
        }

    """
    changes = []
    query = f'**/*{glob.escape(UNIT_START_CHAR)}*{glob.escape(UNIT_END_CHAR)}'

    for path, val in dpath.util.search(obj, query, yielded=True):
        start_idx = path.find(UNIT_START_CHAR)
        end_idx = path.find(UNIT_END_CHAR)

        base_path = path[:start_idx]

        field = _get_field(message, base_path)
        options = _field_options(field)

        if getattr(options, 'unit', None):
            input_unit = path[start_idx+1:end_idx]
            val = Quantity(val, input_unit).to(options.unit).magnitude

        val *= getattr(options, 'scale', 1)

        if field.cpp_type in json_format._INT_TYPES:
            val = int(round(val))

        changes.append((path, base_path, val))

    # Changes include deleting the original path (that included unit)
    # This must be done outside the dpath search loop
    _apply_changes(obj, changes)
    return obj


def decode_quantity(message: Message, obj: dict) -> dict:
    changes = []

    for field, options, path in _cached_option_fields(message.DESCRIPTOR):
        try:
            scale = getattr(options, 'scale', None)
            unit = getattr(options, 'unit', None)
            modified = any([scale, unit])

            if modified:
                val = dpath.util.get(obj, path)
                new_path = None

                if scale:
                    val /= scale

                if unit:
                    q = Quantity(val, options.unit)
                    new_path = f'{path}{UNIT_START_CHAR}{q.units}{UNIT_END_CHAR}'
                    val = q.magnitude

                changes.append((path, new_path, val))

        except KeyError:
            # Value not found in input dict
            # We don't need any conversion
            continue

    _apply_changes(obj, changes)
    return obj


def hex_to_b64(s: str) -> str:
    return b64encode(unhexlify(s)).decode()


def b64_to_hex(s: str) -> str:
    return hexlify(b64decode(s)).decode()
