"""
Input/output modification functions for transcoding
"""

from brewblox_codec_spark import _path_extension  # isort:skip

import glob
from base64 import b64decode, b64encode
from binascii import hexlify, unhexlify
from typing import Any, Callable, Generator, Iterator, List, Optional, Tuple

import dpath
from brewblox_service import brewblox_logger
from google.protobuf import json_format
from google.protobuf.descriptor import DescriptorBase, FieldDescriptor
from google.protobuf.message import Message
from pint import UnitRegistry, quantity

import brewblox_pb2

_path_extension.avoid_lint_errors()
LOGGER = brewblox_logger(__name__)


class Modifier():
    _unit_start_char: str = '['
    _unit_end_char: str = ']'
    _link_start_char: str = '<'
    _link_end_char: str = '>'
    _brewblox_provider: DescriptorBase = brewblox_pb2.brewblox

    def __init__(self, unit_filename: str):
        self._ureg: UnitRegistry = UnitRegistry()
        if unit_filename:
            self._ureg.load_definitions(unit_filename)
            self._ureg.default_system = 'brewblox'
        self._desc_cache: dict = {}

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
        for key, val in dpath.util.search(obj, path, yielded=True):
            dpath.util.set(obj, key, func(val))

        return obj

    @staticmethod
    def _get_field(msg: Message, path: str) -> Message:
        """
        Returns the nested Protobuf field associated with the message and path string.
        """
        descriptor = msg.DESCRIPTOR
        path_list = [s for s in path.split('/') if s]  # drops empty sections

        for p in path_list[:-1]:
            descriptor = descriptor.fields_by_name[p].message_type

        leaf = path_list[-1]
        field = descriptor.fields_by_name[leaf]
        return field

    def _find_option_fields(self, desc: DescriptorBase, path='') -> Generator[Tuple[DescriptorBase, str], None, None]:
        """
        Yields all nested fields in the base descriptor that have Protobuf options.
        """
        if desc.has_options:
            yield desc, self._field_options(desc), path

        if isinstance(desc, FieldDescriptor):
            message = desc.message_type
        else:
            message = desc

        if message:
            for field_name in message.fields_by_name:
                field_desc = message.fields_by_name[field_name]
                field_path = f'{path}/{field_name}'
                yield from self._find_option_fields(field_desc, field_path)

        raise StopIteration()

    def _cached_option_fields(self, desc: DescriptorBase) -> Generator[Tuple[DescriptorBase, str], None, None]:
        """
        Caches _find_option_fields().
        Field definitions are assumed to be immutable at runtime,
        and do not require cache invalidation.
        """
        if desc not in self._desc_cache:
            self._desc_cache[desc] = [t for t in self._find_option_fields(desc)]

        yield from self._desc_cache[desc]

    def _field_options(self, field: FieldDescriptor, provider: FieldDescriptor=None):
        provider = provider or self._brewblox_provider
        return field.GetOptions().Extensions[provider]

    @staticmethod
    def _apply_changes(obj: dict, changes: List[Tuple[str, Optional[str], Any]]) -> dict:
        """
        Modifies the `obj` dict with `changes`.
        Each change is a tuple containing:
        * path:     Current /-separated path to value.
        * new_path: Desired /-separated path to modified value.
                    If this is none, `path` will be updated.
        * val:      The new value.

        Example:
            >>> obj = {'val1': 1, 'val2': 2}
            >>> changes = [
                ('val1', None, 11),
                ('val2', 'newval2', 22)
            ]
            >>> _apply_changes(obj, changes)
            >>> print(obj)
            {
                'val1': 11,
                'newval2': 22
            }
        """
        for (path, new_path, val) in changes:
            if new_path:
                dpath.util.delete(obj, glob.escape(path))
                dpath.util.new(obj, new_path, val)
            else:
                dpath.util.set(obj, path, val)

        return obj

    def _quantity(self, *args, **kwargs) -> quantity._Quantity:
        return self._ureg.Quantity(*args, **kwargs)

    def _preferred_unit(self, unit: str) -> str:
        try:
            return self._settings['units'][unit]
        except KeyError:
            return unit

    def encode_options(self, message: Message, obj: dict) -> dict:
        """
        Modifies `obj` based on Protobuf options and post-fixed unit notations in dict keys.

        Supported Protobuf options:
        * unit:     convert post-fixed unit notation to Protobuf unit
        * scale:    multiply value with scale after unit conversion

        The output is a dict where values use controller units.

        Example:
            >>> values = {
                'settings': {
                    'address': 'FF',
                    'offset[delta_degF]': 20
                }
            }

            >>> encode_options(
                OneWireTempSensor_pb2.OneWireTempSensor(),
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
                    'address': 'FF',  # No options -> not converted
                    'offset': 2844    # Converted to delta_degC, scaled * 256, and rounded to int
                }
            }
        """
        changes = []
        end_chars = self._unit_end_char + self._link_end_char
        # query = f'**/*{glob.escape(self._unit_start_char)}*{glob.escape(self._unit_end_char)}'

        def find_option_keys(it: Iterator[Tuple[str, Any]], path='') -> Iterator[Tuple[str, Any]]:
            # Yields path, val
            for k, v in it:
                subpath = f'{path}/{k}'
                if isinstance(v, list):
                    yield from find_option_keys(enumerate(v), subpath)
                elif isinstance(v, dict):
                    yield from find_option_keys(v.items(), subpath)
                elif str(k)[-1] in end_chars:
                    yield subpath, v

        def encode_units(path, val):
            # strip end char, then split
            base_path, input_unit = path[:-1].split(self._unit_start_char)

            field = self._get_field(message, base_path)
            options = self._field_options(field)

            is_list = isinstance(val, (list, set))

            if not is_list:
                val = [val]

            if getattr(options, 'unit', None):
                val = [self._quantity(v, input_unit).to(options.unit).magnitude for v in val]

            val = [v * getattr(options, 'scale', 1) for v in val]

            if field.cpp_type in json_format._INT_TYPES:
                val = [int(round(v)) for v in val]

            if not is_list:
                val = val[0]

            changes.append((path, base_path, val))

        def encode_link(path, val):
            # Link is already resolved, now strip the name mangling
            base_path = next(path.split(self._link_start_char))
            changes.append((path, base_path, val))

        for path, val in find_option_keys(obj.items()):
            if path.endswith(self._unit_end_char):
                encode_units(path, val)
            elif path.endswith(self._link_end_char):
                encode_link(path, val)

        # Changes include deleting the original path (that included unit)
        # This must be done outside the dpath search loop
        self._apply_changes(obj, changes)
        return obj

    def decode_options(self, message: Message, obj: dict) -> dict:
        """
        Modifies `obj` based on brewblox protobuf options.
        Supported options:
        * scale:   divides value by scale before unit conversion
        * unit:    postfixes dict key with the unit defined in the Protobuf spec

        Example:
            >>> values = {
                'settings': {
                    'address': 'FF',
                    'offset': 2844
                }
            }

            >>> decode_options(
                OneWireTempSensor_pb2.OneWireTempSensor(),
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

            # User preference unit for delta temperature is 'delta_degF'

            >>> print(values)
            {
                'settings': {
                    'address': 'FF',            # No options -> not converted
                    'offset[delta_degF]': 20    # scaled / 256, converted to preference, postfixed with unit
                }
            }
        """
        changes = []

        for field, options, path in self._cached_option_fields(message.DESCRIPTOR):
            try:
                scale = getattr(options, 'scale', None)
                unit = getattr(options, 'unit', None)
                link = getattr(options, 'link', None)
                modified = any([scale, unit, link])

                if modified:
                    val = dpath.util.get(obj, path)
                    new_path = None

                    is_list = isinstance(val, (list, set))

                    if not is_list:
                        val = [val]

                    if scale:
                        val = [v / scale for v in val]

                    if unit:
                        base_unit = self._quantity(options.unit).to_base_units().units
                        new_path = f'{path}{self._unit_start_char}{base_unit}{self._unit_end_char}'
                        val = [
                            self._quantity(v, options.unit)
                            .to_base_units()
                            .magnitude
                            for v in val
                        ]

                    if link:
                        new_path = f'{path}{self._link_start_char}{self._link_end_char}'

                    if not is_list:
                        val = val[0]

                    changes.append((path, new_path, val))

            except KeyError:
                # Value not found in input dict
                # We don't need any conversion
                continue

        self._apply_changes(obj, changes)
        return obj

    @staticmethod
    def hex_to_b64(s: str) -> str:
        return b64encode(unhexlify(s)).decode()

    @staticmethod
    def b64_to_hex(s: str) -> str:
        return hexlify(b64decode(s)).decode()
