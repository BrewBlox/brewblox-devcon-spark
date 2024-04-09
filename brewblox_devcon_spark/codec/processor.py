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

from brewblox_devcon_spark.models import (DecodedPayload, MaskField, MaskMode,
                                          ReadMode)

from . import unit_conversion
from .opts import DateFormatOpt, MetadataOpt
from .pb2 import brewblox_pb2
from .time_utils import serialize_datetime

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class OptionElement():
    field: FieldDescriptor
    """The protobuf field descriptor"""

    obj: dict
    """The raw data in python format"""

    key: str
    """The key for `obj` in python ({key:obj})"""

    base_key: str
    """The key for `obj` with any unit/link postfixes removed

    Example: `key` = 'value[degC]', `base_key` = 'value'
    """

    postfix: str
    """The postfixed content removed from `key` to make `base_key`

    This does not include brackets.
    Example: `key` = 'value[degC]', `postfix` = 'degC'
    """

    address: tuple[int | None]
    """The nested protobuf address, expressed as field tags.

    A None value indicates an address that should not be
    included in a mask. Only leaf nodes should be included
    in an inclusive mask, as a root node mask serves as a wildcard.

    Repeated fields are always considered leaf nodes.

    Example:
        `{
            tag_1: {
                tag_2: {
                    tag_3: True,
                    tag_4: False,
                },
                tag_5: [
                    { tag_6: True },
                    { tag_6: True },
                ],
                tag_7: None,
            },
        }`
        yields addresses:
        - (1,None)
        - (1,2,None)
        - (1,2,3)
        - (1,2,4)
        - (1,5)
        - (1,5,None,6)
        - (1,5,None,6)
        - (1,7)
    """


class ProtobufProcessor():
    _BREWBLOX_PROVIDER: FieldDescriptor = brewblox_pb2.field

    def __init__(self, filter_values=True):
        self._converter = unit_conversion.CV.get()
        self._filter_values = filter_values

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

    @staticmethod
    def matches_address(field: MaskField, match: tuple[int | None]):
        for fa_tag, ma_tag in zip(field.address, match):
            if fa_tag is not None and fa_tag != ma_tag:
                return False
        return True

    @staticmethod
    def unit_name(unit_num: int) -> str:
        return brewblox_pb2.UnitType.Name(unit_num)

    @staticmethod
    def type_name(blockType_num: int) -> str:
        return brewblox_pb2.BlockType.Name(blockType_num)

    def _walk_elements(self,
                       desc: Descriptor,
                       obj: dict,
                       parent_address: tuple[int | None] = (),
                       ) -> Iterator[OptionElement]:
        """
        Recursively walks `obj`, and yields an `OptionElement` for each value.

        The tree is walked depth-first, and iterates over a copy of the initial keyset.
        This makes it safe for calling code to modify or delete the value relevant to them.
        Any entries added to the parent object after an element is yielded will not be considered.
        """
        for key, value in list(obj.items()):
            base_key, postfix = self._postfix_pattern.findall(key)[0]
            field: FieldDescriptor = desc.fields_by_name[base_key]
            address: tuple[int | None] = (*parent_address, field.number)

            # Value field, no need for recursion
            # This is a leaf node
            # obj is { key: ... }
            if not field.message_type:
                yield OptionElement(field, obj, key, base_key, postfix, address)

            # Explicitly deleted submessage field
            # Stop recursion
            # obj is { key: None }
            # Because we stop here, this field is a leaf node
            elif value is None:
                yield OptionElement(field, obj, key, base_key, postfix, address)

            # Repeated fields are generic collections, expressed in json as list or dict
            # Because the list/map index is not a tag, we can't patch inside the repeated field
            # The repeated field itself is a leaf node
            elif field.label == FieldDescriptor.LABEL_REPEATED:

                # map<K, V> field
                # traverse all values
                # The content is serialized as repeated `{ key: K, value: V }` entries
                # obj is { key: {...} }
                if isinstance(value, dict):
                    message_type = field.message_type.fields_by_name['value'].message_type
                    for childobj in value.values():
                        yield from self._walk_elements(message_type, childobj, (*address, None))

                # Generic repeated field
                # traverse all values
                # obj is { key: [{...},{...}] }
                else:
                    for childobj in value:
                        yield from self._walk_elements(field.message_type, childobj, (*address, None))

                yield OptionElement(field, obj, key, base_key, postfix, address)

            # Submessage with content
            # traverse all members
            # obj is { key: {...} }
            # The field itself is not a leaf node
            else:
                yield from self._walk_elements(field.message_type, value, address)
                # This is not a leaf node. Its address should not be included in the mask
                yield OptionElement(field, obj, key, base_key, postfix, (*address, None))

        return

    def _field_options(self, field: FieldDescriptor) -> brewblox_pb2.FieldOpts:
        return field.GetOptions().Extensions[self._BREWBLOX_PROVIDER]

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
                   payload: DecodedPayload, /,
                   filter_values: bool | None = None
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
        if filter_values is None:
            filter_values = self._filter_values

        for element in self._walk_elements(desc, payload.content):
            options = self._field_options(element.field)

            if options.ignored:
                del element.obj[element.key]
                continue

            if filter_values and options.readonly:
                del element.obj[element.key]
                continue

            # We don't support exclusive masks at this level
            # List items are not supported for patching
            # Only insert a field mask for the `repeated` field itself, not its children
            if payload.maskMode == MaskMode.INCLUSIVE and None not in element.address:
                payload.maskFields.append(MaskField(address=list(element.address)))

            def _convert_value(value: Any) -> str | int | float:
                if options.unit:
                    unit_name = self.unit_name(options.unit)
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
                    payload: DecodedPayload, /,
                    mode: ReadMode = ReadMode.DEFAULT,
                    filter_values: bool | None = None,
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
        * logged:       Tag for filtering output data when using ReadMode.LOGGED.
        * stored:       Tag for filtering output data when using ReadMode.STORED.
        * *_invalid_if: Sets value to None if equal to invalid value.

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
                    mode=ReadMode.LOGGED)

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
        metadata_opt = MetadataOpt.TYPED
        date_fmt_opt = DateFormatOpt.ISO8601

        if mode == ReadMode.LOGGED:
            metadata_opt = MetadataOpt.POSTFIX
            date_fmt_opt = DateFormatOpt.SECONDS

        if filter_values is None:
            filter_values = self._filter_values

        for element in self._walk_elements(desc, payload.content):
            options = self._field_options(element.field)

            if payload.maskMode == MaskMode.NO_MASK:
                excluded = False
            elif payload.maskMode in [MaskMode.INCLUSIVE, MaskMode.EXCLUSIVE]:
                masked = any((f for f in payload.maskFields
                              if self.matches_address(f, element.address)))
                excluded = masked ^ (payload.maskMode == MaskMode.INCLUSIVE)
            else:
                raise NotImplementedError(f'{payload.maskMode=}')

            if options.ignored:
                del element.obj[element.key]
                continue

            if filter_values:
                if (mode == ReadMode.STORED and not options.stored) \
                        or (mode == ReadMode.LOGGED and not options.logged):
                    del element.obj[element.key]
                    continue

            link_type = self.type_name(options.objtype)
            qty_system_unit = self.unit_name(options.unit)
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

                    if metadata_opt == MetadataOpt.TYPED:
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

                    if metadata_opt == MetadataOpt.TYPED:
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
                    return serialize_datetime(value, date_fmt_opt)

                return value

            new_key = element.key
            new_value = element.obj[element.key]

            # If metadata is postfixed, we may need to update the key
            if metadata_opt == MetadataOpt.POSTFIX:
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
