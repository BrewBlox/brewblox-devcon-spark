"""
Input/output modification functions for transcoding
"""

import re
from base64 import b64decode, b64encode
from binascii import hexlify, unhexlify
from dataclasses import dataclass
from functools import reduce
from typing import Iterator, List, Optional, Union

from brewblox_service import brewblox_logger
from google.protobuf import json_format
from google.protobuf.descriptor import DescriptorBase, FieldDescriptor
from google.protobuf.message import Message

from .opts import CodecOpts, FilterOpt, MetadataOpt
from .pb2 import brewblox_pb2
from .unit_conversion import UnitConverter

STRIP_FIELDS_KEY = 'strippedFields'

LOGGER = brewblox_logger(__name__)


@dataclass(frozen=True)
class OptionElement():
    field: FieldDescriptor
    obj: dict
    key: str
    base_key: str
    postfix: str
    postfix_arg: str
    nested: bool


class Modifier():
    _BREWBLOX_PROVIDER: DescriptorBase = brewblox_pb2.brewblox

    def __init__(self, converter: UnitConverter, strip_readonly=True):
        self._converter = converter
        self._strip_readonly = strip_readonly

        symbols = re.escape('[]<>')
        self._postfix_pattern = re.compile(''.join([
            f'([^{symbols}]+)',  # "value" -> captured
            f'[{symbols}]?',     # "["
            f'([^{symbols},]*)',  # "degC" -> captured
            ',?',  # option separator
            f'([^{symbols}]*)',  # "driven" -> captured
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

    def _find_options(self, desc: DescriptorBase, obj: dict, nested: bool = False) -> Iterator[OptionElement]:
        """
        Recursively walks `obj`, and yields an `OptionElement` for each value.

        The tree is walked depth-first, and iterates over a copy of the initial keyset.
        This makes it safe for calling code to modify or delete the value relevant to them.
        Any entries added to the parent object after an element is yielded will not be considered.
        """
        for key in set(obj.keys()):
            base_key, postfix, postfix_arg = self._postfix_pattern.findall(key)[0]
            field: FieldDescriptor = desc.fields_by_name[base_key]

            if field.message_type:
                if field.label == FieldDescriptor.LABEL_REPEATED:
                    children = [v for v in obj[key]]
                else:
                    children = [obj[key]]

                for c in children:
                    yield from self._find_options(field.message_type, c, True)

            yield OptionElement(field, obj, key, base_key, postfix, postfix_arg, nested)

        return

    def _field_options(self, field: FieldDescriptor, provider: FieldDescriptor = None):
        provider = provider or self._BREWBLOX_PROVIDER
        return field.GetOptions().Extensions[provider]

    def _unit_name(self, unit_num: int) -> str:
        return brewblox_pb2.BrewBloxTypes.UnitType.Name(unit_num)

    def _objtype_name(self, objtype_num: int) -> str:
        return brewblox_pb2.BrewBloxTypes.BlockType.Name(objtype_num)

    def _encode_unit(self, value: Union[float, dict], unit_type: str, postfix: Optional[str]) -> float:
        if isinstance(value, dict):
            user_value = value['value']
            user_unit = value.get('unit')
            return self._converter.to_sys_value(user_value, unit_type, user_unit)
        else:
            user_unit = postfix
            return self._converter.to_sys_value(value, unit_type, user_unit)

    def encode_options(self, message: Message, obj: dict, opts: CodecOpts) -> dict:
        """
        Modifies `obj` based on Protobuf options and dict key postfixes.

        Supported Protobuf options:
        * unit:         Convert metadata unit notation (postfix or typed object) to Protobuf unit.
        * scale:        Multiply value with scale after unit conversion.
        * objtype:      Strip link key postfix (<TempSensorInterface> or <>), or extract id from typed object.
        * hexed:        Convert hexadecimal string to int64.
        * readonly:     Strip value from protobuf input.
        * ignored:      Strip value from protobuf input.
        * hexstr:       Convert hexadecimal string to base64 string.

        The output is a dict where values use controller units.

        Postfix notations and typed objects can be mixed in the same data.

        Example:
            >>> values = {
                'settings': {
                    'address': 'aabbccdd',
                    'offset[delta_degF]': 20,
                    'sensor<TempSensorInterface>': 10,
                    'output': 9000,
                    'desiredSetting': {
                        '__bloxtype': 'Quantity',
                        'value': 15,
                        'unit': 'degC',
                    },
                },
            }

            >>> encode_options(
                    TempSensorOneWire_pb2.TempSensorOneWire(),
                    values,
                    CodecOpts())

            # ExampleMessage.proto:
            #
            # message ExampleMessage {
            #   message Settings {
            #     fixed64 address = 1 [(brewblox).hexed = true];
            #     sint32 offset = 2 [(brewblox).unit = DeltaTemp, (brewblox).scale = 256];
            #     uint16 sensor = 3 [(brewblox).objtype = TempSensorInterface];
            #     sint32 output = 4 [(brewblox).readonly = true];
            #     sint32 desiredSetting = 5 [(brewblox).unit = Temp];
            #   }
            # ...

            >>> print(values)
            {
                'settings': {
                    'address': 2864434397,  # Converted from Hex to int64
                    'offset': 2844,         # Converted to delta_degC, scaled * 256, and rounded to int
                    'sensor': 10,           # Object type postfix stripped
                                            # 'output' is readonly -> stripped from dict
                    'desiredSetting': 15,   # No conversion required - value already used degC
                }
            }
        """
        for element in self._find_options(message.DESCRIPTOR, obj):
            options = self._field_options(element.field)
            val = element.obj[element.key]
            new_key = element.base_key

            if options.ignored:
                del element.obj[element.key]
                continue

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

            if options.unit:
                unit_name = self._unit_name(options.unit)
                val = [
                    self._encode_unit(v, unit_name, element.postfix or None)
                    for v in val
                ]

            if options.objtype:
                val = [
                    v['id'] if isinstance(v, dict) else v
                    for v in val
                ]

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

    def decode_options(self, message: Message, obj: dict, opts: CodecOpts) -> dict:
        """
        Post-processes protobuf data based on protobuf / codec options.

        Supported protobuf options:
        * scale:        Divides value by scale before unit conversion.
        * unit:         Adds unit to output, using either a [] postfix, or a typed object.
        * objtype:      Adds object type to output, using either a <> postfix, or a typed object.
        * driven        Adds the "driven" flag to postfix or typed object.
        * hexed:        Converts base64 decoder output to int.
        * hexstr:       Converts base64 decoder output to hexadecimal string.
        * readonly:     Ignored: decoding means reading from controller.
        * ignored:      Strip value from output.
        * logged:       Tag for filtering output data.

        Supported special field names:
        * strippedFields:  lists all fields that should be set to None in the current message.

        Supported codec options:
        * filter:       If opts.filter == LOGGED, all values without options.logged are stripped from output.
        * metadata:     Format used to serialize object metadata.
                        Determines whether units/links are postfixed or rendered as typed object.

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
                    values,
                    CodecOpts(metadata=MetadataOpt.POSTFIX))

            # ExampleMessage.proto:
            #
            # message ExampleMessage {
            #   message Settings {
            #     fixed64 address = 1 [(brewblox).hexed = true];
            #     sint32 offset = 2 [(brewblox).unit = "delta_degC", (brewblox).scale = 256];
            #     uint16 sensor = 3 [(brewblox).objtype = TempSensorInterface];
            #     sint32 output = 4 [(brewblox).readonly = true];
            #   }
            # ...

            # User preference unit for delta temperature is 'delta_degF'

            >>> print(values)
            {
                'settings': {
                    'address': 'aabbccdd',              # Converted from base64 string to hex string
                    'offset[delta_degF]': 20            # Scaled / 256, converted to preference, postfixed with unit
                    'sensor<TempSensorInterface>': 10,  # Postfixed with obj type
                    'output': 1234,                     # We're reading -> keep readonly values
                }
            }
        """
        stripped_fields = obj.pop(STRIP_FIELDS_KEY, [])

        for element in self._find_options(message.DESCRIPTOR, obj):
            options = self._field_options(element.field)
            val = element.obj[element.key]
            new_key = element.key
            stripped = element.field.number in stripped_fields and not element.nested

            if options.ignored:
                del element.obj[element.key]
                continue

            if opts.filter == FilterOpt.LOGGED and not options.logged:
                del element.obj[element.key]
                continue

            is_list = isinstance(val, (list, set))

            if not is_list:
                val = [val]

            if options.scale:
                val = [v / options.scale for v in val]

            if options.unit:
                unit_name = self._unit_name(options.unit)
                user_unit = self._converter.to_user_unit(unit_name)

                # Always convert value
                val = [
                    self._converter.to_user_value(v, unit_name)
                    for v in val
                ]

                if opts.metadata == MetadataOpt.TYPED:
                    shared = {
                        '__bloxtype': 'Quantity',
                        'unit': user_unit,
                    }
                    if options.readonly:
                        shared['readonly'] = True

                    val = [{**shared, 'value': v if not stripped else None} for v in val]

                if opts.metadata == MetadataOpt.POSTFIX:
                    new_key += f'[{user_unit}]'

            if options.objtype:
                objtype = self._objtype_name(options.objtype)

                if opts.metadata == MetadataOpt.TYPED:
                    shared = {
                        '__bloxtype': 'Link',
                        'type': objtype,
                    }
                    if options.driven:
                        shared['driven'] = True

                    val = [{**shared, 'id': v if not stripped else None} for v in val]

                if opts.metadata == MetadataOpt.POSTFIX:
                    postfix = f'<{objtype},driven>' if options.driven else f'<{objtype}>'
                    new_key += postfix

            if options.hexed:
                val = [self.int_to_hex(v) for v in val]

            if options.hexstr:
                val = [self.b64_to_hex(v) for v in val]

            if not is_list:
                val = val[0]

            if element.key != new_key:
                del element.obj[element.key]

            if stripped:
                if (options.unit or options.objtype) and opts.metadata == MetadataOpt.TYPED:
                    pass  # Already handled
                else:
                    val = None

            element.obj[new_key] = val

        return obj
