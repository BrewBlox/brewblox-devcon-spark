"""
Input/output modification functions for transcoding
"""

import ipaddress
import logging
import re
from base64 import b64decode, b64encode
from binascii import hexlify, unhexlify
from collections.abc import Iterator
from dataclasses import dataclass
from functools import reduce
from socket import htonl, ntohl
from typing import Any

from google.protobuf import json_format
from google.protobuf.descriptor import Descriptor, FieldDescriptor

from brewblox_devcon_spark import exceptions, utils
from brewblox_devcon_spark.models import DecodedPayload, ReadMode

from . import bloxfield, unit_conversion
from .descriptors import is_map, is_optional, json_default, list_wrapper, options
from .opts import DateFormatOpt
from .pb2 import brewblox_pb2
from .time_utils import serialize_datetime

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class OptionElement:
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

    wrapper: FieldDescriptor | None
    """The list wrapper field, if `field` is the `items` field of a flattened wrapper

    The API shows a wrapper (`{items: [...]}`) as its bare list or map.
    """


def is_null(value: Any) -> bool:
    """None, or a typed Quantity or Link without value: absent when encoding"""
    return (
        value is None
        or (bloxfield.is_quantity(value) and value.get('value') is None)
        or (bloxfield.is_link(value) and value.get('id') is None)
    )


class ProtobufProcessor:
    def __init__(self, filter_values=True):
        self._converter = unit_conversion.CV.get()
        self._filter_values = filter_values

        symbols = re.escape('[]<>')
        self._postfix_pattern = re.compile(
            ''.join(
                [
                    f'([^{symbols}]+)',  # "value" -> captured
                    f'[{symbols}]?',  # "["
                    f'([^{symbols},]*)',  # "degC" -> captured
                    f',?[^{symbols}]*',  # ",driven" -> (backwards compatibility)
                    f'[{symbols}]?',  # "]"
                ]
            )
        )

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
    def unit_name(unit_num: int) -> str:
        return brewblox_pb2.UnitType.Name(unit_num)

    @staticmethod
    def type_name(blockType_num: int) -> str:
        return brewblox_pb2.BlockType.Name(blockType_num)

    def _walk_elements(self, desc: Descriptor, obj: dict) -> Iterator[OptionElement]:
        """
        Recursively walks `obj`, and yields an `OptionElement` for each value.

        The tree is walked depth-first, and iterates over a copy of the initial keyset.
        This makes it safe for calling code to modify or delete the value relevant to them.
        Any entries added to the parent object after an element is yielded will not be considered.

        List wrappers are flattened in `obj`: the wrapper key holds the bare list or map.
        The walk uses the wrapper's `items` field in its place,
        so maps, typed links, and postfixes in the list work as for any repeated field.
        """
        for key, value in list(obj.items()):
            base_key, postfix = self._postfix_pattern.findall(key)[0]
            field: FieldDescriptor = desc.fields_by_name[base_key]
            wrapper: FieldDescriptor | None = None

            if items := list_wrapper(field):
                wrapper, field = field, items

            # Value field, no need for recursion
            # obj is { key: ... }
            if not field.message_type or value is None:
                yield OptionElement(field, obj, key, base_key, postfix, wrapper)

            # Repeated fields are generic collections, expressed in json as list or dict
            elif field.label == FieldDescriptor.LABEL_REPEATED:
                # map<K, V> field
                # traverse all values
                # The content is serialized as repeated `{ key: K, value: V }` entries
                # obj is { key: {...} }
                if isinstance(value, dict):
                    message_type = field.message_type.fields_by_name['value'].message_type
                    for childobj in value.values():
                        yield from self._walk_elements(message_type, childobj)

                # Generic repeated field
                # traverse all values
                # obj is { key: [{...},{...}] }
                else:
                    for childobj in value:
                        yield from self._walk_elements(field.message_type, childobj)

                yield OptionElement(field, obj, key, base_key, postfix, wrapper)

            # Submessage with content
            # traverse all members
            # obj is { key: {...} }
            else:
                yield from self._walk_elements(field.message_type, value)
                yield OptionElement(field, obj, key, base_key, postfix, wrapper)

    def _encode_unit(self, value: float | dict, unit_type: str, postfix: str | None) -> float:
        if isinstance(value, dict):
            user_value = value['value']
            user_unit = value.get('unit')
            return self._converter.to_sys_value(user_value, unit_type, user_unit)
        user_unit = postfix
        return self._converter.to_sys_value(value, unit_type, user_unit)

    def pre_encode(
        self, desc: Descriptor, payload: DecodedPayload, /, filter_values: bool | None = None
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

        The output is the same payload object, but with modified content.
        Content values use controller units.

        Writes are by presence: absent keys are not encoded, and the controller keeps their value.
        None, and typed Quantity or Link objects without a value, are absent.
        List wrappers are given as their bare list or map, and encoded as `{items: ...}`.
        An empty list is kept: it sends a present, empty wrapper that clears the list.

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
            opts = options(element.field)

            if opts.ignored:
                del element.obj[element.key]
                continue

            if filter_values and opts.readonly:
                del element.obj[element.key]
                continue

            def _convert_value(value: Any) -> str | int | float:
                if opts.unit:
                    unit_name = self.unit_name(opts.unit)
                    value = self._encode_unit(value, unit_name, element.postfix or None)

                if opts.objtype:
                    if isinstance(value, dict):
                        value = value['id']

                if opts.scale:
                    value *= opts.scale

                if opts.hexed:
                    value = self.hex_to_int(value)

                if opts.hexstr:
                    value = self.hex_to_b64(value)

                if opts.ipv4address:
                    value = self.ipv4_to_int(value)

                if opts.datetime:
                    value = serialize_datetime(value, DateFormatOpt.SECONDS)

                if element.field.cpp_type in json_format._INT_TYPES:
                    value = int(round(value))

                return value

            new_key = element.base_key
            new_value = element.obj[element.key]

            # Writes are by presence: an absent key keeps the stored value.
            # None, and a typed Quantity or Link without value, are absent.
            if is_null(new_value):
                del element.obj[element.key]
                continue

            try:
                if isinstance(new_value, (list, set)):
                    new_value = [_convert_value(v) for v in new_value if not is_null(v)]
                else:
                    new_value = _convert_value(new_value)
            except Exception as ex:
                # Name the field: conversion errors are otherwise raised as a
                # bare TypeError/ValueError with no clue which value caused them
                raise exceptions.EncodeException(
                    f'{element.field.full_name}: {utils.strex(ex)} (value={new_value!r})'
                ) from ex

            # The key changed if postfixed metadata was used
            if element.key != new_key:
                del element.obj[element.key]

            # An empty list stays: it sends a present, empty wrapper that clears the list
            if element.wrapper is not None:
                new_value = {'items': new_value}

            element.obj[new_key] = new_value

        return payload

    def fill(self, desc: Descriptor, obj: dict, /, mode: ReadMode = ReadMode.DEFAULT) -> dict:
        """
        Completes MessageToDict output in place, before post_decode.

        MessageToDict never emits an unset optional field, or an unset singular message.
        * An absent optional readonly field is invalid, and becomes None.
        * An absent optional writable field gets its default value.
          Not in CHANGED reads: there, absent means unchanged.
        * A list wrapper is replaced by its bare list or map.
          An absent wrapper becomes an empty list or map, except in CHANGED reads.
          A CHANGED decode sets the covered wrappers present first, so only uncovered wrappers stay absent.

        Present singular messages are filled recursively.
        List elements and map values are not: their fields have no presence.
        """
        for field in desc.fields:
            key = field.name
            present = key in obj

            if is_optional(field):
                if present:
                    continue
                if options(field).readonly:
                    obj[key] = None
                elif mode != ReadMode.CHANGED:
                    obj[key] = json_default(field, integer_enums=(mode == ReadMode.STORED))

            elif items := list_wrapper(field):
                if present:
                    obj[key] = obj[key]['items']
                elif mode != ReadMode.CHANGED:
                    obj[key] = {} if is_map(items) else []

            elif present and field.message_type and field.label != FieldDescriptor.LABEL_REPEATED:
                self.fill(field.message_type, obj[key], mode)

        return obj

    def post_decode(
        self,
        desc: Descriptor,
        payload: DecodedPayload,
        /,
        mode: ReadMode = ReadMode.DEFAULT,
        filter_values: bool | None = None,
    ) -> DecodedPayload:
        """
        Post-processes protobuf data based on protobuf / codec options.
        The content is expected to be completed by `fill()` first.

        Supported protobuf options:
        * scale:        Divides value by scale before unit conversion.
        * unit:         Converts to the user unit, and outputs a typed Quantity object.
        * objtype:      Outputs a typed Link object.
        * hexed:        Converts base64 decoder output to int.
        * hexstr:       Converts base64 decoder output to hexadecimal string.
        * datetime:     Converts value to an ISO-8601 string.
        * ipv4address:  Converts integer IP address to dot string notation.
        * readonly:     Ignored: decoding means reading from controller.
        * ignored:      Strip value from output.
        * stored:       Tag for filtering output data when using ReadMode.STORED.
        * omit_if_zero: Strip value from output if zero.
        * null_if_zero: Sets value to None if zero.

        None is the invalid marker: the value of an absent optional readonly field.
        Quantities and links keep their typed object, with a None value or id.

        Example:
            >>> values = {
                'settings': {
                    'address': 2864434397,
                    'offset': 2844,
                    'sensor': 10,
                    'output': 1234,
                    'invalid': None,
                }
            }

            >>> post_decode(
                    ExampleMessage_pb2.ExampleMessage(),
                    values)

            # ExampleMessage.proto:
            #
            # message ExampleMessage {
            #   message Settings {
            #     fixed64 address = 1 [(brewblox).hexed = true];
            #     sint32 offset = 2 [(brewblox).unit = "delta_degC", (brewblox).scale = 256];
            #     uint16 sensor = 3 [(brewblox).objtype = TempSensorInterface];
            #     sint32 output = 4 [(brewblox).readonly = true];
            #     optional sint32 invalid = 5 [(brewblox).unit = "degC", (brewblox).readonly = true];
            #   }
            # ...

            # User preference unit for delta temperature is 'delta_degF'

            >>> print(values)
            {
                'settings': {
                    'address': 'aabbccdd',  # Converted from base64 string to hex string
                    'offset': {             # Scaled / 256, converted to preference
                        '__bloxtype': 'Quantity',
                        'unit': 'delta_degF',
                        'value': 20,
                    },
                    'sensor': {
                        '__bloxtype': 'Link',
                        'type': 'TempSensorInterface',
                        'id': 10,
                    },
                    'output': 1234,         # We're reading -> keep readonly values
                    'invalid': {
                        '__bloxtype': 'Quantity',
                        'unit': 'degF',
                        'value': None,
                        'readonly': True,
                    },
                }
            }

        """
        if filter_values is None:
            filter_values = self._filter_values

        for element in self._walk_elements(desc, payload.content):
            opts = options(element.field)

            if opts.ignored:
                del element.obj[element.key]
                continue

            if filter_values and mode == ReadMode.STORED and not opts.stored:
                del element.obj[element.key]
                continue

            link_type = self.type_name(opts.objtype)
            qty_system_unit = self.unit_name(opts.unit)
            qty_user_unit = self._converter.to_user_unit(qty_system_unit)

            def _convert_value(value: float | int | str | None) -> float | int | str | dict | None:
                # None is the invalid marker: absent optional readonly fields are filled with None
                if value is None or (opts.null_if_zero and value == 0):
                    value = None
                else:
                    if opts.scale:
                        value /= opts.scale

                    if opts.unit:
                        value = self._converter.to_user_value(value, qty_system_unit)
                    elif opts.hexed:
                        value = self.int_to_hex(value)
                    elif opts.hexstr:
                        value = self.b64_to_hex(value)
                    elif opts.ipv4address:
                        value = self.int_to_ipv4(value)
                    elif opts.datetime:
                        value = serialize_datetime(value, DateFormatOpt.ISO8601)

                # Invalid quantities and links keep their typed shell
                if opts.unit:
                    value = {'__bloxtype': 'Quantity', 'unit': qty_user_unit, 'value': value}
                    if opts.readonly:
                        value['readonly'] = True

                elif opts.objtype:
                    value = {'__bloxtype': 'Link', 'type': link_type, 'id': value}

                return value

            new_value = element.obj[element.key]

            # Filter values that should be omitted entirely
            if opts.omit_if_zero:
                if isinstance(new_value, (list, set)):
                    new_value = [v for v in new_value if v != 0]
                elif new_value == 0:
                    del element.obj[element.key]
                    continue

            # Convert value
            try:
                if isinstance(new_value, (list, set)):
                    new_value = [_convert_value(v) for v in new_value]
                else:
                    new_value = _convert_value(new_value)
            except Exception as ex:
                # Name the field. Decoding never raises to the caller: this is
                # folded into the ErrorObject stub, so the message is all we get
                raise exceptions.DecodeException(
                    f'{element.field.full_name}: {utils.strex(ex)} (value={new_value!r})'
                ) from ex

            element.obj[element.key] = new_value

        return payload
