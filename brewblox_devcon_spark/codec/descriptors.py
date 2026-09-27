"""
Descriptor analysis for presence, list wrappers, CHANGED coverage, and logged fields.

Descriptors are immutable singletons in the compiled protobuf pool,
so every result is cached per descriptor.

"API shape" is the JSON devcon emits and accepts:
a list wrapper field (`{items: [...]}`) shows as its bare list or map.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from types import MappingProxyType
from typing import Any

from google.protobuf import json_format
from google.protobuf.descriptor import Descriptor, FieldDescriptor
from google.protobuf.message_factory import GetMessageClass

from .pb2 import brewblox_pb2


@dataclass(frozen=True)
class CoverageNode:
    field: FieldDescriptor
    """The API-shape field. For a covered wrapper, this is the wrapper field."""

    children: Mapping[str, 'CoverageNode'] | None = None
    """
    The covered fields of a traversed singular message.
    None for a covered value: a leaf, or a list or wrapper that is replaced whole.
    """


@dataclass(frozen=True)
class LoggedNode:
    field: FieldDescriptor

    children: Mapping[str, 'LoggedNode'] | None
    """The logged fields of message values (singular or list elements). None for a leaf."""

    skip_changed: bool
    """Only included in history on full reads."""


@cache
def options(field: FieldDescriptor) -> brewblox_pb2.FieldOpts:
    return field.GetOptions().Extensions[brewblox_pb2.field]


@cache
def is_optional(field: FieldDescriptor) -> bool:
    """
    A proto3 `optional` field: a non-message field in a synthetic oneof named `_<name>`.
    The upb FieldDescriptor exposes neither `proto3_optional` nor `is_synthetic`.
    A guard test compares this with `proto3_optional` in the DescriptorProto.
    """
    oneof = field.containing_oneof
    return (
        field.message_type is None and oneof is not None and oneof.name == f'_{field.name}' and len(oneof.fields) == 1
    )


def is_map(field: FieldDescriptor) -> bool:
    return field.message_type is not None and field.message_type.GetOptions().map_entry


def value_type(field: FieldDescriptor) -> Descriptor | None:
    """The message type of the field's values. For a map, that of the map values."""
    if is_map(field):
        return field.message_type.fields_by_name['value'].message_type
    return field.message_type


@cache
def list_wrapper(field: FieldDescriptor) -> FieldDescriptor | None:
    """
    The `items` field if `field` is a list wrapper, otherwise None.
    A list wrapper is a singular message field whose type has exactly one field:
    a repeated field (maps included) named `items`.
    """
    msg = field.message_type
    if msg is None or field.is_repeated or len(msg.fields) != 1:
        return None
    items = msg.fields[0]
    if items.name == 'items' and items.is_repeated:
        return items
    return None


@cache
def json_default(field: FieldDescriptor, *, integer_enums: bool) -> Any:
    """The value MessageToDict gives `field` when it is set to its default."""
    message = GetMessageClass(field.containing_type)()
    setattr(message, field.name, field.default_value)
    decoded = json_format.MessageToDict(
        message,
        preserving_proto_field_name=True,
        use_integers_for_enums=integer_enums,
    )
    return decoded[field.name]


def is_writable(field: FieldDescriptor) -> bool:
    """Neither readonly nor ignored: a write encodes it"""
    opts = options(field)
    return not (opts.readonly or opts.ignored)


def reset_value(field: FieldDescriptor) -> Any:
    """
    The value in proto shape that resets `field` to its default in a write (outside list elements).

    * A leaf: its default, which ParseDict sets present (0, false, '', enum 0).
    * A list wrapper: present and empty. For a map wrapper, a write that merges by key keeps the map.
    * A repeated field: empty. It has no presence: an empty list is not sent.
    * A singular message: present, with every writable leaf reset, recursively.
      Members of a oneof are left out: none of them is the default.
    """
    if items := list_wrapper(field):
        return {'items': {} if is_map(items) else []}
    if field.is_repeated:
        return {} if is_map(field) else []
    if field.message_type:
        return {
            f.name: reset_value(f)
            for f in field.message_type.fields
            if is_writable(f) and (f.containing_oneof is None or is_optional(f))
        }
    return field.default_value


@cache
def is_covered(field: FieldDescriptor) -> bool:
    """
    Whether a CHANGED read carries the field, or a leaf inside it.
    A leaf is covered when it is readonly, and neither ignored nor skip_changed.
    An ignored or skip_changed message field prunes its subtree.
    """
    opts = options(field)
    if opts.ignored or opts.skip_changed:
        return False
    msg = value_type(field)
    if msg is None:
        return opts.readonly
    return bool(coverage(msg))


@cache
def coverage(desc: Descriptor) -> Mapping[str, CoverageNode]:
    """
    The covered fields of `desc`, in API shape.

    A singular message field (not a wrapper) with covered descendants is traversed:
    its node has children. Anything else covered is a value node:
    a covered leaf, or a repeated field or wrapper whose elements are replaced whole.
    """
    nodes = {}
    for field in desc.fields:
        if not is_covered(field):
            continue
        if field.message_type and not field.is_repeated and not list_wrapper(field):
            nodes[field.name] = CoverageNode(field, coverage(field.message_type))
        else:
            nodes[field.name] = CoverageNode(field)
    return MappingProxyType(nodes)


@cache
def traversed_messages(desc: Descriptor) -> tuple[tuple[str, ...], ...]:
    """
    Proto paths of the singular message fields that a CHANGED read traverses:
    messages with covered descendants, and covered wrappers.
    Parents come before their children.
    """
    paths = []
    for name, node in coverage(desc).items():
        if node.children is not None:
            paths.append((name,))
            paths.extend((name, *sub) for sub in traversed_messages(node.field.message_type))
        elif list_wrapper(node.field):
            paths.append((name,))
    return tuple(paths)


@cache
def logged_fields(desc: Descriptor) -> Mapping[str, LoggedNode]:
    """
    The logged fields of `desc`.
    A field is logged when it and all its ancestors are marked logged.
    No logged field is a list wrapper, a map, or a repeated leaf (test_logged_fields_are_plain),
    so the proto shape is the API shape.
    """
    nodes = {}
    for field in desc.fields:
        opts = options(field)
        if opts.logged:
            msg = field.message_type
            nodes[field.name] = LoggedNode(field, logged_fields(msg) if msg else None, opts.skip_changed)
    return MappingProxyType(nodes)
