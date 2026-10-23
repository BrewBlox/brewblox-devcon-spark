"""
Builds fully populated protobuf messages for codec tests.
"""

from collections.abc import Iterator
from itertools import count

from google.protobuf.descriptor import FieldDescriptor
from google.protobuf.message import Message

from brewblox_devcon_spark.codec import descriptors


def _scalar(field: FieldDescriptor, n: int) -> float | bool | str | bytes:  # noqa: PLR0911
    opts = descriptors.options(field)

    if field.enum_type:
        return next((v.number for v in field.enum_type.values if v.number != 0), 0)  # noqa: PD011
    if field.type == FieldDescriptor.TYPE_BOOL:
        return True
    if field.type == FieldDescriptor.TYPE_STRING:
        return f's{n}'
    if field.type == FieldDescriptor.TYPE_BYTES:
        return bytes([n % 256, 0xAB])
    if field.cpp_type in (FieldDescriptor.CPPTYPE_FLOAT, FieldDescriptor.CPPTYPE_DOUBLE):
        return n + 0.5
    if opts.objtype:
        return 100 + n
    if opts.datetime:
        return 1_700_000_000 + n
    return n * 1000 + 1


def populate(message: Message, counter: Iterator[int] | None = None) -> Message:
    """
    Sets every field of `message` to a valid non-zero value, recursively.
    Repeated fields and maps get one element, and a oneof gets its first member.
    The values are deterministic: logged_golden.json was generated with them.
    """
    counter = counter or count(1)

    for field in message.DESCRIPTOR.fields:
        oneof = field.containing_oneof
        if oneof is not None and not descriptors.is_optional(field) and oneof.fields[0] is not field:
            continue

        n = next(counter)
        if descriptors.is_map(field):
            value_field = field.message_type.fields_by_name['value']
            key_field = field.message_type.fields_by_name['key']
            key = f'k{n}' if key_field.type == FieldDescriptor.TYPE_STRING else n
            container = getattr(message, field.name)
            if value_field.message_type:
                populate(container[key], counter)
            else:
                container[key] = _scalar(value_field, n)
        elif field.is_repeated:
            container = getattr(message, field.name)
            if field.message_type:
                populate(container.add(), counter)
            else:
                container.append(_scalar(field, n))
        elif field.message_type:
            child = getattr(message, field.name)
            child.SetInParent()
            populate(child, counter)
        else:
            setattr(message, field.name, _scalar(field, n))

    return message


def _copy(message: Message) -> Message:
    copy = type(message)()
    copy.CopyFrom(message)
    return copy


def _zeroed(message: Message) -> Iterator[Message]:
    """
    Copies of a populated `message`, each with one member of a oneof set to its default.
    Members that are messages are also set with each of their own zeroed copies.
    Proto3 `optional` fields are not oneof members here.
    """
    for field in message.DESCRIPTOR.fields:
        if field.is_repeated:
            continue
        member = field.containing_oneof is not None and not descriptors.is_optional(field)

        if field.message_type is None:
            if member:
                copy = _copy(message)
                setattr(copy, field.name, field.default_value)
                yield copy
            continue

        if member:
            copy = _copy(message)
            copy.ClearField(field.name)
            getattr(copy, field.name).SetInParent()
            yield copy

        # A member that is not set is populated first
        child = (
            getattr(message, field.name)
            if message.HasField(field.name)
            else populate(getattr(_copy(message), field.name))
        )
        for zeroed in _zeroed(child):
            copy = _copy(message)
            getattr(copy, field.name).CopyFrom(zeroed)
            yield copy


def add_zero_members(message: Message) -> Message:
    """
    Adds elements to every list and map of messages in a populated `message`, recursively:
    copies of its first element, each with one member of a oneof set to its default (`_zeroed`).
    A DEFAULT read shows some of these as null (a zero datetime, or no link once link ids are resolved).
    """
    for field in message.DESCRIPTOR.fields:
        value_type = descriptors.value_type(field)
        if value_type is None:
            continue
        container = getattr(message, field.name)

        if descriptors.is_map(field):
            for value in container.values():
                add_zero_members(value)
            for key, value in list(container.items())[:1]:
                for idx, zeroed in enumerate(_zeroed(value)):
                    container[f'{key}_zero{idx}'].CopyFrom(zeroed)
        elif field.is_repeated:
            for element in container:
                add_zero_members(element)
            container.extend([zeroed for element in container[:1] for zeroed in _zeroed(element)])
        elif message.HasField(field.name):
            add_zero_members(container)

    return message
