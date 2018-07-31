"""
Input/output modification functions for transcoding
"""

from brewblox_codec_spark import _path_extension  # isort:skip

import re
from base64 import b64decode, b64encode
from binascii import hexlify, unhexlify
from contextlib import suppress
from typing import Callable, Iterator

import dpath
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

    @staticmethod
    def modify_if_present(obj: dict, path: str, func: Callable) -> dict:
        """
        Replaces a value in a (possibly nested) dict.

        If path is invalid, no values are changed.

        Example:
            >>> input = {'nested': { 'collection': { 'value': 0 }}}
            >>> output = modify_if_present(
                            obj=input,
                            path='nested/collection/value',
                            func=lambda v: v + 1
                        )
            >>> print(output)
            {'nested': { 'collection': { 'value': 1 }}}
            >>> print(input)
            {'nested': { 'collection': { 'value': 1 }}}
        """
        val = dpath.util.get(obj, path)
        dpath.util.new(obj, path, func(val))

        return obj

    def _find_options(self, desc: DescriptorBase, obj) -> Iterator[OptionElement]:
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

    def _quantity(self, *args, **kwargs) -> quantity._Quantity:
        return self._ureg.Quantity(*args, **kwargs)

    def encode_options(self, message: Message, obj: dict) -> dict:
        """
        Modifies `obj` based on Protobuf options and dict key postfixes.

        Supported Protobuf options:
        * unit:     convert post-fixed unit notation ([UNIT]) to Protobuf unit
        * scale:    multiply value with scale after unit conversion
        * link:     strip link key postfix (<>)

        The output is a dict where values use controller units.

        Example:
            >>> values = {
                'settings': {
                    'address': 'FF',
                    'offset[delta_degF]': 20,
                    'sensor<>': 10
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
            #     bytes address = 1;
            #     sint32 offset = 2 [(brewblox).unit = "delta_degC", (brewblox).scale = 256];
            #     uint16 sensor = 3 [(brewblox).link = "SensorType"];
            #   }
            # ...

            >>> print(values)
            {
                'settings': {
                    'address': 'FF',  # No options -> not converted
                    'offset': 2844,   # Converted to delta_degC, scaled * 256, and rounded to int
                    'sensor': 10      # Link postfix stripped
                }
            }
        """
        for element in self._find_options(message.DESCRIPTOR, obj):
            options = self._field_options(element.field)
            val = element.obj[element.key]

            is_list = isinstance(val, (list, set))

            if not is_list:
                val = [val]

            if options.unit and element.postfix:
                val = [self._quantity(v, element.postfix).to(options.unit).magnitude for v in val]

            if options.scale:
                val = [v * options.scale for v in val]

            if element.field.cpp_type in json_format._INT_TYPES:
                val = [int(round(v)) for v in val]

            if not is_list:
                val = val[0]

            if element.key != element.base_key:
                del element.obj[element.key]

            element.obj[element.base_key] = val

        return obj

    def decode_options(self, message: Message, obj: dict) -> dict:
        """
        Modifies `obj` based on brewblox protobuf options.
        Supported options:
        * scale:   divides value by scale before unit conversion
        * unit:    postfixes dict key with the unit defined in the Protobuf spec
        * link:    postfixes dict key with triangle brackets (<>)

        Example:
            >>> values = {
                'settings': {
                    'address': 'FF',
                    'offset': 2844,
                    'sensor': 10
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
            #     bytes address = 1;
            #     sint32 offset = 2 [(brewblox).unit = "delta_degC", (brewblox).scale = 256];
            #     uint16 sensor = 3 [(brewblox).link = "SensorType"];
            #   }
            # ...

            # User preference unit for delta temperature is 'delta_degF'

            >>> print(values)
            {
                'settings': {
                    'address': 'FF',            # No options -> not converted
                    'offset[delta_degF]': 20    # scaled / 256, converted to preference, postfixed with unit
                    'sensor<>': 10              # Postfixed with link indicator
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
                print(options.link)
                new_key += '<>'

            if not is_list:
                val = val[0]

            if element.key != new_key:
                del element.obj[element.key]

            element.obj[new_key] = val

        return obj
