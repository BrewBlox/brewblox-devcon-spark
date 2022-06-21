"""
Protobuf messages coupled to their respective type identities
"""


from dataclasses import dataclass
from typing import Generator, Optional, Type

from google.protobuf.message import Message
from google.protobuf.reflection import GeneratedProtocolMessageType

from . import pb2

BlockType = pb2.brewblox_pb2.BlockType


@dataclass(frozen=True)
class InterfaceLookup:
    type_str: str
    type_int: int


@dataclass(frozen=True)
class ObjectLookup:
    type_str: str
    type_int: int
    subtype_str: Optional[str]
    subtype_int: Optional[int]
    message_cls: Type[Message]


def _interface_lookup_generator() -> Generator[InterfaceLookup, None, None]:
    for blockType in BlockType.values():
        yield InterfaceLookup(
            type_str=BlockType.Name(blockType),
            type_int=blockType,
        )


def _object_lookup_generator() -> Generator[ObjectLookup, None, None]:
    for pb in [getattr(pb2, k) for k in pb2.__all__]:
        members = [getattr(pb, k)
                   for k in dir(pb)
                   if not k.startswith('_')]
        messages = [el
                    for el in members
                    if isinstance(el, GeneratedProtocolMessageType)]

        for msg_cls in messages:
            desc = msg_cls.DESCRIPTOR
            opts = desc.GetOptions().Extensions[pb2.brewblox_pb2.msg]
            if opts.objtype:
                yield ObjectLookup(
                    type_str=BlockType.Name(opts.objtype),
                    type_int=opts.objtype,
                    subtype_str=(desc.name if opts.subtype else None),
                    subtype_int=opts.subtype,
                    message_cls=msg_cls,
                )


OBJECT_LOOKUPS: list[ObjectLookup] = [
    # Actual objects
    *_object_lookup_generator(),

    # Custom test objects
    ObjectLookup(
        type_str='EdgeCase',
        type_int=9001,
        subtype_str=None,
        subtype_int=0,
        message_cls=pb2.EdgeCase_pb2.Block,
    ),
    ObjectLookup(
        type_str='EdgeCase',
        type_int=9001,
        subtype_str='SubCase',
        subtype_int=1,
        message_cls=pb2.EdgeCase_pb2.SubCase,
    ),
]

INTERFACE_LOOKUPS: list[InterfaceLookup] = [
    *_interface_lookup_generator(),

    # Custom test objects
    InterfaceLookup(
        type_str='EdgeCase',
        type_int=9001,
    ),
]
