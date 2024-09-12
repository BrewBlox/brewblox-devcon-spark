"""
Protobuf messages coupled to their respective type identities
"""


from contextvars import ContextVar
from dataclasses import dataclass
from typing import Generator, Type

from google.protobuf.descriptor import Descriptor, FileDescriptor
from google.protobuf.internal.enum_type_wrapper import EnumTypeWrapper
from google.protobuf.message import Message

from . import pb2

BlockType: EnumTypeWrapper = pb2.brewblox_pb2.BlockType

# Block type values below this are reserved for interfaces
# They will not be associated with actual messages
BLOCK_INTERFACE_TYPE_END = 255


CV_OBJECTS: ContextVar[list['ObjectLookup']] = ContextVar('lookup.objects')
CV_INTERFACES: ContextVar[list['InterfaceLookup']] = ContextVar('lookup.interfaces')
CV_COMBINED: ContextVar[list['InterfaceLookup']] = ContextVar('lookup.combined')


@dataclass(frozen=True)
class InterfaceLookup:
    type_str: str
    type_int: int


@dataclass(frozen=True)
class ObjectLookup:
    type_str: str
    type_int: int
    message_cls: Type[Message]


def _interface_lookup_generator() -> Generator[InterfaceLookup, None, None]:
    for block_type in BlockType.values():
        if block_type <= BLOCK_INTERFACE_TYPE_END:
            yield InterfaceLookup(
                type_str=BlockType.Name(block_type),
                type_int=block_type,
            )


def _object_lookup_generator() -> Generator[ObjectLookup, None, None]:
    for pb_module in [getattr(pb2, k) for k in pb2.__all__]:
        file_desc: FileDescriptor = pb_module.DESCRIPTOR
        messages: dict[str, Descriptor] = file_desc.message_types_by_name

        for msg_name, msg_desc in messages.items():
            msg_cls: Message = getattr(pb_module, msg_name)
            opts = msg_desc.GetOptions().Extensions[pb2.brewblox_pb2.msg]
            if opts.objtype:
                yield ObjectLookup(
                    type_str=BlockType.Name(opts.objtype),
                    type_int=opts.objtype,
                    message_cls=msg_cls,
                )


def setup():
    objects: list[ObjectLookup] = [
        # Actual objects
        *_object_lookup_generator(),

        # Custom test objects
        ObjectLookup(
            type_str='EdgeCase',
            type_int=9001,
            message_cls=pb2.EdgeCase_pb2.Block,
        ),
    ]

    interfaces: list[InterfaceLookup] = [
        *_interface_lookup_generator(),

        # Custom test objects
        InterfaceLookup(
            type_str='EdgeCase',
            type_int=9001,
        ),
    ]

    combined: list[InterfaceLookup] = [
        *objects,
        *interfaces,
    ]

    CV_OBJECTS.set(objects)
    CV_INTERFACES.set(interfaces)
    CV_COMBINED.set(combined)
