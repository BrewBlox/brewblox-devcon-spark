"""
Input/output modification functions for transcoding
"""

from brewblox_devcon_spark.codec import _path_extension  # isort:skip

import re
from binascii import hexlify, unhexlify
from contextlib import suppress
from functools import reduce
from typing import Iterator, List

from brewblox_service import brewblox_logger
from dataclasses import dataclass
from google.protobuf import json_format
from google.protobuf.descriptor import DescriptorBase, FieldDescriptor
from google.protobuf.message import Message
from pint import UndefinedUnitError, UnitRegistry, quantity

import brewblox_pb2

_path_extension.avoid_lint_errors()
LOGGER = brewblox_logger(__name__)


@dataclass(frozen=True)
class OptionElement():
    field: FieldDescriptor
    obj: dict
    key: str
    base_key: str
    postfix: str


class Modifier():
    _BREWBLOX_PROVIDER: DescriptorBase = brewblox_pb2.brewblox

    def __init__(self, unit_filename: str, strip_readonly=True):
        self._ureg: UnitRegistry = UnitRegistry(autoconvert_offset_to_baseunit=True)
        self._strip_readonly = strip_readonly
        if unit_filename:
            self._ureg.load_definitions(unit_filename)
            self._ureg.default_system = 'brewblox'

        symbols = re.escape('[]<>')
        self._postfix_pattern = re.compile(''.join([
            f'([^{symbols}]+)',  # "value" -> captured
            f'[{symbols}]?',     # "["
            f'([^{symbols}]*)',  # "degC" -> captured
            f'[{symbols}]?',     # "]"
        ]))

    @staticmethod
    def hex_to_int(s: str) -> int:
        return int.from_bytes(unhexlify(s), 'little')

    @staticmethod
    def int_to_hex(i: int) -> str:
        return hexlify(int(i).to_bytes(8, 'little')).decode()

    @staticmethod
    def pack_bit_flags(flags: List[int]) -> int:
        if next((i for i in flags if i >= 8), None):
            raise ValueError(f'Invalid bit flags in {flags}. Values must be 0-7.')
        return reduce(lambda result, idx: result | 1 << idx, flags, 0)

    @staticmethod
    def unpack_bit_flags(flags: int) -> List[int]:
        return [i for i in range(8) if 1 << i & flags]

    def _quantity(self, *args, **kwargs) -> quantity._Quantity:
        return self._ureg.Quantity(*args, **kwargs)

    def _find_options(self, desc: DescriptorBase, obj: dict) -> Iterator[OptionElement]:
        """
        Recursively walks `obj`, and yields an `OptionElement` for each value.

        The tree is walked depth-first, and iterates over a copy of the initial keyset.
        This makes it safe for calling code to modify or delete the value relevant to them.
        Any entries added to the parent object after an element is yielded will not be considered.
        """
        for key in set(obj.keys()):
            base_key, option_value = self._postfix_pattern.findall(key)[0]
            field: FieldDescriptor = desc.fields_by_name[base_key]

            if field.message_type:
                if field.label == FieldDescriptor.LABEL_REPEATED:
                    children = [v for v in obj[key]]
                else:
                    children = [obj[key]]

                for c in children:
                    yield from self._find_options(field.message_type, c)

            yield OptionElement(field, obj, key, base_key, option_value)

        raise StopIteration()

    def _field_options(self, field: FieldDescriptor, provider: FieldDescriptor=None):
        provider = provider or self._BREWBLOX_PROVIDER
        return field.GetOptions().Extensions[provider]

    def encode_options(self, message: Message, obj: dict) -> dict:
        """
        Modifies `obj` based on Protobuf options and dict key postfixes.

        Supported Protobuf options:
        * unit:     convert post-fixed unit notation ([UNIT]) to Protobuf unit
        * scale:    multiply value with scale after unit conversion
        * link:     strip link key postfix (<>)
        * hexed:    convert hexadecimal string to int64
        * readonly: strip value from protobuf input

        The output is a dict where values use controller units.

        Example:
            >>> values = {
                'settings': {
                    'address': 'aabbccdd',
                    'offset[delta_degF]': 20,
                    'sensor<>': 10,
                    'output': 9000,
                }
            }

            >>> encode_options(
                TempSensorOneWire_pb2.TempSensorOneWire(),
                values
            )

            # ExampleMessage.proto:
            #
            # message ExampleMessage {
            #   message Settings {
            #     fixed64 address = 1 [(brewblox).hexed = true];
            #     sint32 offset = 2 [(brewblox).unit = "delta_degC", (brewblox).scale = 256];
            #     uint16 sensor = 3 [(brewblox).link = "SensorType"];
            #     sint32 output = 4 [(brewblox).readonly = true];
            #   }
            # ...

            >>> print(values)
            {
                'settings': {
                    'address': 2864434397,  # Converted from Hex to int64
                    'offset': 2844,         # Converted to delta_degC, scaled * 256, and rounded to int
                    'sensor': 10            # Link postfix stripped
                                            # 'output' is readonly -> stripped from dict
                }
            }
        """
        for element in self._find_options(message.DESCRIPTOR, obj):
            options = self._field_options(element.field)
            val = element.obj[element.key]
            new_key = element.base_key

            is_list = isinstance(val, (list, set))

            if not is_list:
                val = [val]

            if options.unit and element.postfix:
                val = [self._quantity(v, element.postfix).to(options.unit).magnitude for v in val]

            if options.scale:
                val = [v * options.scale for v in val]

            if options.hexed:
                val = [self.hex_to_int(v) for v in val]

            if element.field.cpp_type in json_format._INT_TYPES:
                val = [int(round(v)) for v in val]

            if not is_list:
                val = val[0]

            if element.key != new_key:
                del element.obj[element.key]

            if options.readonly and self._strip_readonly:
                # Replace with the same type, but empty
                val = type(val)()

            element.obj[new_key] = val

        return obj

    def decode_options(self, message: Message, obj: dict) -> dict:
        """
        Modifies `obj` based on brewblox protobuf options.
        Supported options:
        * scale:        divides value by scale before unit conversion
        * unit:         postfixes dict key with the unit defined in the Protobuf spec
        * link:         postfixes dict key with triangle brackets (<>)
        * hexed:        converts base64 decoder output to hexadecimal string
        * readonly:     ignored: decoding means reading from controller

        Example:
            >>> values = {
                'settings': {
                    'address': 2864434397,
                    'offset': 2844,
                    'sensor': 10,
                    'output': 1234,
                }
            }

            >>> decode_options(
                ExampleMessage_pb2.ExampleMessage(),
                values
            )

            # ExampleMessage.proto:
            #
            # message ExampleMessage {
            #   message Settings {
            #     fixed64 address = 1 [(brewblox).hexed = true];
            #     sint32 offset = 2 [(brewblox).unit = "delta_degC", (brewblox).scale = 256];
            #     uint16 sensor = 3 [(brewblox).link = "SensorType"];
            #     sint32 output = 4 [(brewblox).readonly = true];
            #   }
            # ...

            # User preference unit for delta temperature is 'delta_degF'

            >>> print(values)
            {
                'settings': {
                    'address': 'aabbccdd',      # Converted from base64 string to hex string
                    'offset[delta_degF]': 20    # Scaled / 256, converted to preference, postfixed with unit
                    'sensor<>': 10,             # Postfixed with link indicator
                    'output': 1234,             # We're reading -> keep readonly values
                }
            }
        """
        for element in self._find_options(message.DESCRIPTOR, obj):
            options = self._field_options(element.field)
            val = element.obj[element.key]
            new_key = element.key

            is_list = isinstance(val, (list, set))

            if not is_list:
                val = [val]

            if options.scale:
                val = [v / options.scale for v in val]

            if options.unit:
                base_unit = str(self._quantity(options.unit).to_base_units().units)

                # The Pint to_base_units() function doesn't retain delta units.
                # If the base unit is degC, then quantity('delta_degF').to_base_units() yields degC.
                # We catch UndefinedUnitError because not all base units have a delta.
                # 'delta_degK', for example, does not exist.
                if options.unit.lower().startswith('delta_'):
                    with suppress(UndefinedUnitError):
                        delta_base = 'delta_' + base_unit
                        self._quantity(delta_base)
                        base_unit = delta_base

                new_key += '[' + base_unit + ']'
                val = [
                    self._quantity(v, options.unit)
                    .to(base_unit)
                    .magnitude
                    for v in val
                ]

            if options.link:
                new_key += '<>'

            if options.hexed:
                val = [self.int_to_hex(v) for v in val]

            if not is_list:
                val = val[0]

            if element.key != new_key:
                del element.obj[element.key]

            element.obj[new_key] = val

        return obj
