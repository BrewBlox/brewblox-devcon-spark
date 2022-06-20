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


# class Transcoder(ABC):

#     def __init__(self, proc: ProtobufProcessor):
#         self.proc = proc

#     @abstractclassmethod
#     def type_int(cls) -> int:
#         """
#         The numerical enum value for `blockType`
#         """

#     @abstractclassmethod
#     def type_str(cls) -> str:
#         """
#         The string enum value for `blockType`.
#         """

#     @classmethod
#     def subtype_int(cls) -> int:
#         """
#         Alternative messages must declare a `subtype` that is unique within `blockType`.
#         """
#         return 0

#     @classmethod
#     def subtype_str(cls) -> Optional[str]:
#         """
#         Alternative messages must declare a `subtype` that is unique within `blockType`.
#         `subtype` itself is not an enum, so the name of the Protobuf message is used.
#         Naturally, the Protobuf message name must also be unique within the namespace.

#         If `subtype` is 0, the subtype name is None.
#         This is applicable for the default Block messages.
#         """
#         return None

#     @classmethod
#     def type_impl(cls) -> list[str]:
#         return []

#     @abstractmethod
#     def encode(self, values: dict) -> bytes:
#         """
#         Encode a Python dict to bytes.
#         """

#     @abstractmethod
#     def decode(self, encoded: bytes, opts: DecodeOpts) -> dict:
#         """
#         Decode bytes to a Python dict.
#         """

#     @classmethod
#     def get(cls, identifier: Identifier_, proc: ProtobufProcessor) -> 'Transcoder':
#         blockType, subtype = identifier
#         for trc in _TRANSCODERS:
#             if blockType == trc.type_str() or blockType == trc.type_int():
#                 if subtype == trc.subtype_str() or subtype == trc.subtype_int():
#                     return trc(proc)
#         raise KeyError(f'No transcoder found for identifier {identifier}')


# class BlockInterfaceTranscoder(Transcoder):

#     @classmethod
#     def type_int(cls) -> int:
#         return cls._ENUM_VAL

#     @classmethod
#     def type_str(cls) -> str:
#         return pb2.brewblox_pb2.BlockType.Name(cls._ENUM_VAL)

#     def encode(self, values: dict) -> bytes:
#         return b'\x00'

#     def decode(self, values: bytes, _: DecodeOpts) -> dict:
#         return dict()


# class DeprecatedObjectTranscoder(Transcoder):

#     @classmethod
#     def type_int(cls) -> int:
#         return 65533

#     @classmethod
#     def type_str(cls) -> str:
#         return 'DeprecatedObject'

#     def encode(self, values: dict) -> bytes:
#         actual_id = values['actualId']
#         encoded = actual_id.to_bytes(2, 'little')
#         return encoded

#     def decode(self, encoded: bytes, _: DecodeOpts) -> dict:
#         actual_id = int.from_bytes(encoded, 'little')
#         return {'actualId': actual_id}


# class BaseProtobufTranscoder(Transcoder):

#     @classmethod
#     def descriptor(cls) -> Descriptor:
#         return cls._MESSAGE_TYPE.DESCRIPTOR

#     @classmethod
#     def message(cls) -> Message:
#         return cls._MESSAGE_TYPE()

#     @classmethod
#     def _message_opts(cls) -> pb2.brewblox_pb2.MessageOpts:
#         # Message opts as set in BrewbloxMessageOptions in brewblox.proto
#         return cls.descriptor().GetOptions().Extensions[pb2.brewblox_pb2.msg]

#     @classmethod
#     def type_int(cls) -> int:
#         return cls._message_opts().objtype

#     @classmethod
#     def type_str(cls) -> str:
#         return BlockType.Name(cls.type_int())

#     @classmethod
#     def type_impl(cls) -> list[str]:
#         return [BlockType.Name(i) for i in cls._message_opts().impl]

#     @classmethod
#     def subtype_int(cls) -> int:
#         return cls._message_opts().subtype

#     @classmethod
#     def subtype_str(cls) -> Optional[str]:
#         if cls.subtype_int():
#             return cls.descriptor().name
#         else:
#             return None

#     def encode(self, values: dict) -> bytes:
#         # LOGGER.debug(f'encoding {values} to {self.__class__._MESSAGE_TYPE}')
#         obj = json_format.ParseDict(values, self.message())
#         data = obj.SerializeToString()
#         return data

#     def decode(self, encoded: bytes, opts: DecodeOpts) -> dict:
#         int_enum = opts.enums == ProtoEnumOpt.INT

#         msg = self.message()
#         msg.ParseFromString(encoded)
#         decoded = json_format.MessageToDict(
#             message=msg,
#             preserving_proto_field_name=True,
#             including_default_value_fields=True,
#             use_integers_for_enums=int_enum,
#         )
#         # LOGGER.debug(f'decoded {self.__class__._MESSAGE_TYPE} to {decoded}')
#         return decoded


# class ControlboxRequestTranscoder(BaseProtobufTranscoder):
#     _MESSAGE_TYPE = pb2.command_pb2.Request

#     @classmethod
#     def type_int(cls) -> int:
#         return REQUEST_TYPE_INT  # never a payload

#     @classmethod
#     def type_str(cls) -> str:
#         return REQUEST_TYPE

#     def encode(self, values: dict) -> bytes:
#         opcode = values.get('opcode')
#         if isinstance(opcode, Enum):
#             values['opcode'] = opcode.name
#         return super().encode(values)


# class ControlboxResponseTranscoder(BaseProtobufTranscoder):
#     _MESSAGE_TYPE = pb2.command_pb2.Response

#     @classmethod
#     def type_int(cls) -> int:
#         return RESPONSE_TYPE_INT  # never a payload

#     @classmethod
#     def type_str(cls) -> str:
#         return RESPONSE_TYPE

#     def encode(self, values: dict) -> bytes:
#         error = values.get('error')
#         if isinstance(error, Enum):
#             values['error'] = error.name
#         return super().encode(values)


# class ProtobufTranscoder(BaseProtobufTranscoder):

#     def encode(self, values: dict) -> bytes:
#         self.proc.pre_encode(self.descriptor(), values)
#         return super().encode(values)

#     def decode(self, encoded: bytes, opts: DecodeOpts) -> dict:
#         decoded = super().decode(encoded, opts)
#         self.proc.post_decode(self.descriptor(), decoded, opts)
#         return decoded


# class EdgeCaseTranscoder(ProtobufTranscoder):
#     _MESSAGE_TYPE = pb2.EdgeCase_pb2.Block

#     @classmethod
#     def type_int(cls) -> int:
#         return 9001

#     @classmethod
#     def type_str(cls) -> str:
#         return 'EdgeCase'


# class EdgeCaseSubTranscoder(EdgeCaseTranscoder):
#     _MESSAGE_TYPE = pb2.EdgeCase_pb2.SubCase


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
]