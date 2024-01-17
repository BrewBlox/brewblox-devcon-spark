"""
Input/output modification functions for transcoding
"""

import ipaddress
import logging
import re
from base64 import b64decode, b64encode
from binascii import hexlify, unhexlify
from dataclasses import dataclass
from functools import reduce
from socket import htonl, ntohl
from typing import Any, Iterator

from google.protobuf import json_format
from google.protobuf.descriptor import Descriptor, FieldDescriptor

from brewblox_devcon_spark.models import DecodedPayload, MaskMode

from . import unit_conversion
from .opts import DateFormatOpt, DecodeOpts, FilterOpt, MetadataOpt
from .pb2 import brewblox_pb2
from .time_utils import serialize_datetime

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class OptionElement():
    field: FieldDescriptor
    obj: dict
    key: str
    base_key: str
    postfix: str
    nested: bool


class ProtobufProcessor():
    _BREWBLOX_PROVIDER: FieldDescriptor = brewblox_pb2.field

    def __init__(self, strip_readonly=True):
        self._converter = unit_conversion.CV.get()
        self._strip_readonly = strip_readonly

        symbols = re.escape('[]<>')
        self._postfix_pattern = re.compile(''.join([
            f'([^{symbols}]+)',     # "value" -> captured
            f'[{symbols}]?',        # "["
            f'([^{symbols},]*)',    # "degC" -> captured
            f',?[^{symbols}]*',     # ",driven" -> (backwards compatibility)
            f'[{symbols}]?',        # "]"
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
    def ipv4_to_int(ip: str) -> int:
        return ntohl(int(ipaddress.ip_address(ip)))

    @staticmethod
    def int_to_ipv4(ip: int) -> str:
        return ipaddress.ip_address(htonl(ip)).compressed

    @staticmethod
    def pack_bit_flags(flags: list[int]) -> int:
        if next((i for i in flags if i >= 8), None):
            raise ValueError(f'Invalid bit flags in {flags}. Values must be 0-7.')
        return reduce(lambda result, idx: result | 1 << idx, flags, 0)

    @staticmethod
    def unpack_bit_flags(flags: int) -> list[int]:
        return [i for i in range(8) if 1 << i & flags]

    def _find_elements(self, desc: Descriptor, obj: dict, nested: bool = False) -> Iterator[OptionElement]:
        """
        Recursively walks `obj`, and yields an `OptionElement` for each value.

        The tree is walked depth-first, and iterates over a copy of the initial keyset.
        This makes it safe for calling code to modify or delete the value relevant to them.
        Any entries added to the parent object after an element is yielded will not be considered.
        """
        for key in set(obj.keys()):
            base_key, postfix = self._postfix_pattern.findall(key)[0]
            field: FieldDescriptor = desc.fields_by_name[base_key]

            if field.message_type:
                if field.label == FieldDescriptor.LABEL_REPEATED:
                    children = [v for v in obj[key]]
                else:
                    children = [obj[key]]

                for c in children:
                    yield from self._find_elements(field.message_type, c, True)

            yield OptionElement(field, obj, key, base_key, postfix, nested)

        return

    def _field_options(self, field: FieldDescriptor) -> brewblox_pb2.FieldOpts:
        return field.GetOptions().Extensions[self._BREWBLOX_PROVIDER]

    def _unit_name(self, unit_num: int) -> str:
        return brewblox_pb2.UnitType.Name(unit_num)

    def _type_name(self, blockType_num: int) -> str:
        return brewblox_pb2.BlockType.Name(blockType_num)

    def _encode_unit(self, value: float | dict, unit_type: str, postfix: str | None) -> float:
        if isinstance(value, dict):
            user_value = value['value']
            user_unit = value.get('unit')
            return self._converter.to_sys_value(user_value, unit_type, user_unit)
        else:
            user_unit = postfix
            return self._converter.to_sys_value(value, unit_type, user_unit)

    def pre_encode(self,
                   desc: Descriptor,
                   payload: DecodedPayload,
                   ) -> DecodedPayload:
        """
        Modifies `payload` based on Protobuf options and dict key postfixes.

        Supported Protobuf options:
        * unit:         Convert metadata unit notation (postfix or typed object) to Protobuf unit.
        * scale:        Multiply value with scale after unit conversion.
        * objtype:      Strip link key postfix (<TempSensorInterface> or <>), or extract id from typed object.
        * hexed:        Convert hexadecimal string to int64.
        * readonly:     Strip value from protobuf input.
        * ignored:      Strip value from protobuf input.
        * hexstr:       Convert hexadecimal string to base64 string.
        * datetime:     Convert ms / s / ISO-8601 value to seconds since UTC.
        * ipv4address:  Converts dot string notation to integer IP address.

        The output is the same payload object, but with modified content and mask.
        Content values use controller units.

        Postfix notations and typed objects can be mixed in the same data.

        Example:
            >>> payload.content = {
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

            >>> pre_encode(
                    TempSensorOneWire_pb2.TempSensorOneWire(),
                    payload)

            # ExampleMessage.proto:
            #
            # message ExampleMessage {
            #   message Settings {
            #     fixed64 address = 1 [(brewblox).hexed = true];
            #     sint32 offset = 2 [(brewblox).unit = DeltaTemp, (brewblox).scale = 256];
            #     uint16 sensor = 3 [(brewblox).blockType = TempSensorInterface];
            #     sint32 output = 4 [(brewblox).readonly = true];
            #     sint32 desiredSetting = 5 [(brewblox).unit = Temp];
            #   }
            # ...

            >>> print(payload.content)
            {
                'settings': {
                    'address': 2864434397,  # Converted from Hex to int64
                    'offset': 2844,         # Converted to delta_degC, scaled * 256, and rounded to int
                    'sensor': 10,           # Object type postfix excluded
                                            # 'output' is readonly -> excluded from dict
                    'desiredSetting': 15,   # No conversion required - value already used degC
                }
            }
        """
        for element in self._find_elements(desc, payload.content):
            options = self._field_options(element.field)

            if options.ignored:
                del element.obj[element.key]
                continue

            if options.readonly and self._strip_readonly:
                del element.obj[element.key]
                continue

            # We don't support exclusive masks at this level
            if payload.maskMode == MaskMode.INCLUSIVE and not element.nested:
                payload.mask.append(element.field.number)

            def _convert_value(value: Any) -> str | int | float:
                if options.unit:
                    unit_name = self._unit_name(options.unit)
                    value = self._encode_unit(value, unit_name, element.postfix or None)

                if options.objtype:
                    if isinstance(value, dict):
                        value = value['id']

                if options.scale:
                    value *= options.scale

                if options.hexed:
                    value = self.hex_to_int(value)

                if options.hexstr:
                    value = self.hex_to_b64(value)

                if options.ipv4address:
                    value = self.ipv4_to_int(value)

                if options.datetime:
                    value = serialize_datetime(value, DateFormatOpt.SECONDS)

                if element.field.cpp_type in json_format._INT_TYPES:
                    value = int(round(value))

                return value

            new_key = element.base_key
            new_value = element.obj[element.key]

            if new_value is None:
                del element.obj[element.key]
                continue

            if isinstance(new_value, (list, set)):
                new_value = [_convert_value(v)
                             for v in new_value
                             if v is not None]
            else:
                new_value = _convert_value(new_value)

            # The key changed if postfixed metadata was used
            if element.key != new_key:
                del element.obj[element.key]

            element.obj[new_key] = new_value

        return payload

    def post_decode(self,
                    desc: Descriptor,
                    payload: DecodedPayload,
                    opts: DecodeOpts,
                    ) -> DecodedPayload:
        """
        Post-processes protobuf data based on protobuf / codec options.

        Supported protobuf options:
        * scale:        Divides value by scale before unit conversion.
        * unit:         Adds unit to output, using either a [] postfix, or a typed object.
        * objtype:      Adds object type to output, using either a <> postfix, or a typed object.
        * hexed:        Converts base64 decoder output to int.
        * hexstr:       Converts base64 decoder output to hexadecimal string.
        * datetime:     Convert value to formatting specified by opts.dates.
        * ipv4address:  Converts integer IP address to dot string notation.
        * readonly:     Ignored: decoding means reading from controller.
        * ignored:      Strip value from output.
        * logged:       Tag for filtering output data.
        * *_invalid_if: Sets value to None if equal to invalid value.

        Supported codec options:
        * filter:       If opts.filter == LOGGED, all values without options.logged are excluded from output.
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

            >>> post_decode(
                    ExampleMessage_pb2.ExampleMessage(),
                    values,
                    DecodeOpts(metadata=MetadataOpt.POSTFIX))

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
        for element in self._find_elements(desc, payload.content):
            options = self._field_options(element.field)

            if payload.maskMode == MaskMode.NO_MASK or element.nested:
                excluded = False
            elif payload.maskMode == MaskMode.INCLUSIVE:
                excluded = element.field.number not in payload.mask
            elif payload.maskMode == MaskMode.EXCLUSIVE:
                excluded = element.field.number in payload.mask
            else:
                raise NotImplementedError(f'{payload.maskMode=}')

            if options.ignored:
                del element.obj[element.key]
                continue

            if opts.filter == FilterOpt.LOGGED and not options.logged:
                del element.obj[element.key]
                continue

            link_type = self._type_name(options.objtype)
            qty_system_unit = self._unit_name(options.unit)
            qty_user_unit = self._converter.to_user_unit(qty_system_unit)

            def _convert_value(value: float | int | str) -> float | int | str | None:
                null_value = options.null_if_zero and value == 0

                if options.scale:
                    value /= options.scale

                if options.unit:
                    if excluded or null_value:
                        value = None
                    else:
                        value = self._converter.to_user_value(value, qty_system_unit)

                    if opts.metadata == MetadataOpt.TYPED:
                        value = {
                            '__bloxtype': 'Quantity',
                            'unit': qty_user_unit,
                            'value': value
                        }

                        if options.readonly:
                            value['readonly'] = True

                    return value

                if options.objtype:
                    if excluded or null_value:
                        value = None

                    if opts.metadata == MetadataOpt.TYPED:
                        value = {
                            '__bloxtype': 'Link',
                            'type': link_type,
                            'id': value,
                        }

                    return value

                if excluded or null_value:
                    return None

                if options.hexed:
                    return self.int_to_hex(value)

                if options.hexstr:
                    return self.b64_to_hex(value)

                if options.ipv4address:
                    return self.int_to_ipv4(value)

                if options.datetime:
                    return serialize_datetime(value, opts.dates)

                return value

            new_key = element.key
            new_value = element.obj[element.key]

            # If metadata is postfixed, we may need to update the key
            if opts.metadata == MetadataOpt.POSTFIX:
                if options.objtype:
                    new_key = f'{element.key}<{link_type}>'
                if options.unit:
                    new_key = f'{element.key}[{qty_user_unit}]'

            # Filter values that should be omitted entirely
            if options.omit_if_zero:
                if isinstance(new_value, (list, set)):
                    new_value = [v for v in new_value if v != 0]
                elif new_value == 0:
                    del element.obj[element.key]
                    continue

            # Convert value
            if isinstance(new_value, (list, set)):
                new_value = [_convert_value(v) for v in new_value]
            else:
                new_value = _convert_value(new_value)

            # Remove old key/value if we updated the key
            if element.key != new_key:
                del element.obj[element.key]

            element.obj[new_key] = new_value

        return payload
