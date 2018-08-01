"""
Input/output modification functions for transcoding
"""

from brewblox_codec_spark import _path_extension  # isort:skip

import re
from base64 import b64decode, b64encode
from binascii import hexlify, unhexlify
from contextlib import suppress
from typing import Iterator

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

    def __init__(self, unit_filename: str):
        self._ureg: UnitRegistry = UnitRegistry()
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
    def hex_to_b64(s: str) -> str:
        return b64encode(unhexlify(s)).decode()

    @staticmethod
    def b64_to_hex(s: str) -> str:
        return hexlify(b64decode(s)).decode()

    def _quantity(self, *args, **kwargs) -> quantity._Quantity:
        return self._ureg.Quantity(*args, **kwargs)

    def _find_options(self, desc: DescriptorBase, obj) -> Iterator[OptionElement]:
        """
        Recursively walks `obj`, and yields an `OptionElement` for each value
        where the associated Protobuf message has an option.

        The tree is walked depth-first, and iterates over a copy of the initial keyset.
        This makes it safe for calling code to modify or delete the value relevant to them.
        Any entries added to the parent object after an element is yielded will not be considered.
        """
        if not isinstance(obj, dict):
            raise StopIteration()

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

            if field.has_options:
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
        * hexed:    convert hexadecimal string to base64 (protobuf input)
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
                OneWireTempSensor_pb2.OneWireTempSensor(),
                values
            )

            # ExampleMessage.proto:
            #
            # message ExampleMessage {
            #   message Settings {
            #     bytes address = 1 [(brewblox).hexed = true];
            #     sint32 offset = 2 [(brewblox).unit = "delta_degC", (brewblox).scale = 256];
            #     uint16 sensor = 3 [(brewblox).link = "SensorType"];
            #     sint32 output = 4 [(brewblox).readonly = true];
            #   }
            # ...

            >>> print(values)
            {
                'settings': {
                    'address': 'qrvM3Q==',  # Converted from Hex to base64
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

            if options.readonly:
                del element.obj[element.key]
                continue

            is_list = isinstance(val, (list, set))

            if not is_list:
                val = [val]

            if options.unit and element.postfix:
                val = [self._quantity(v, element.postfix).to(options.unit).magnitude for v in val]

            if options.scale:
                val = [v * options.scale for v in val]

            if options.hexed:
                val = [self.hex_to_b64(v) for v in val]

            if element.field.cpp_type in json_format._INT_TYPES:
                val = [int(round(v)) for v in val]

            if not is_list:
                val = val[0]

            if element.key != new_key:
                del element.obj[element.key]

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
                    'address': 'qrvM3Q==',
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
            #     bytes address = 1 [(brewblox).hexed = true];
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
                val = [self.b64_to_hex(v) for v in val]

            if not is_list:
                val = val[0]

            if element.key != new_key:
                del element.obj[element.key]

            element.obj[new_key] = val

        return obj
