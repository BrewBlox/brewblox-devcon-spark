"""
Input/output modification functions for transcoding
"""

from brewblox_devcon_spark.codec import _path_extension  # isort:skip

import re
from base64 import b64decode, b64encode
from binascii import hexlify, unhexlify
from functools import reduce
from typing import Iterator, List

from brewblox_service import brewblox_logger
from google.protobuf import json_format
from google.protobuf.descriptor import DescriptorBase, FieldDescriptor
from google.protobuf.message import Message

import brewblox_pb2
from brewblox_devcon_spark.codec.unit_conversion import UnitConverter
from dataclasses import dataclass

STRIP_UNLOGGED_KEY = 'strip_unlogged'

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

    def __init__(self, converter: UnitConverter, strip_readonly=True):
        self._converter = converter
        self._strip_readonly = strip_readonly

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
    def hex_to_b64(s: str) -> str:
        return b64encode(unhexlify(s)).decode()

    @staticmethod
    def b64_to_hex(s: str) -> str:
        return hexlify(b64decode(s)).decode()

    @staticmethod
    def pack_bit_flags(flags: List[int]) -> int:
        if next((i for i in flags if i >= 8), None):
            raise ValueError(f'Invalid bit flags in {flags}. Values must be 0-7.')
        return reduce(lambda result, idx: result | 1 << idx, flags, 0)

    @staticmethod
    def unpack_bit_flags(flags: int) -> List[int]:
        return [i for i in range(8) if 1 << i & flags]

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

        return

    def _field_options(self, field: FieldDescriptor, provider: FieldDescriptor = None):
        provider = provider or self._BREWBLOX_PROVIDER
        return field.GetOptions().Extensions[provider]

    def _unit_name(self, unit_num: int) -> str:
        return brewblox_pb2.BrewbloxFieldOptions.UnitType.Name(unit_num)

    def _link_name(self, link_num: int) -> str:
        return brewblox_pb2.BrewbloxFieldOptions.LinkType.Name(link_num)

    def encode_options(self, message: Message, obj: dict, codec_opts: dict) -> dict:
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
                    'sensor<TempSensorLink>': 10,
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
            #     uint16 sensor = 3 [(brewblox).link = TempSensorLink];
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

            if options.readonly and self._strip_readonly:
                del element.obj[element.key]
                continue

            is_list = isinstance(val, (list, set))

            if not is_list:
                val = [val]

            val = [v for v in val if v is not None]

            if not val:
                del element.obj[element.key]
                continue

            if options.unit and element.postfix:
                unit = self._unit_name(options.unit)
                val = [self._converter.to_sys(v, unit, element.postfix) for v in val]

            if options.scale:
                val = [v * options.scale for v in val]

            if options.hexed:
                val = [self.hex_to_int(v) for v in val]

            if options.hexstr:
                val = [self.hex_to_b64(v) for v in val]

            if element.field.cpp_type in json_format._INT_TYPES:
                val = [int(round(v)) for v in val]

            if not is_list:
                val = val[0]

            if element.key != new_key:
                del element.obj[element.key]

            element.obj[new_key] = val

        return obj

    def decode_options(self, message: Message, obj: dict, codec_opts: dict) -> dict:
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
            #     uint16 sensor = 3 [(brewblox).link = TempSensorLink];
            #     sint32 output = 4 [(brewblox).readonly = true];
            #   }
            # ...

            # User preference unit for delta temperature is 'delta_degF'

            >>> print(values)
            {
                'settings': {
                    'address': 'aabbccdd',        # Converted from base64 string to hex string
                    'offset[delta_degF]': 20      # Scaled / 256, converted to preference, postfixed with unit
                    'sensor<TempSensorLink>': 10, # Postfixed with link type
                    'output': 1234,               # We're reading -> keep readonly values
                }
            }
        """
        strip_unlogged = codec_opts.get(STRIP_UNLOGGED_KEY)

        for element in self._find_options(message.DESCRIPTOR, obj):
            options = self._field_options(element.field)
            val = element.obj[element.key]
            new_key = element.key

            if not options.logged and strip_unlogged:
                del element.obj[element.key]
                continue

            is_list = isinstance(val, (list, set))

            if not is_list:
                val = [val]

            if options.scale:
                val = [v / options.scale for v in val]

            if options.unit:
                unit = self._unit_name(options.unit)
                new_key += '[' + self._converter.user_unit(unit) + ']'
                val = [
                    self._converter.to_user(v, unit)
                    for v in val
                ]

            if options.link:
                new_key += f'<{self._link_name(options.link)}>'

            if options.hexed:
                val = [self.int_to_hex(v) for v in val]

            if options.hexstr:
                val = [self.b64_to_hex(v) for v in val]

            if not is_list:
                val = val[0]

            if element.key != new_key:
                del element.obj[element.key]

            element.obj[new_key] = val

        return obj
