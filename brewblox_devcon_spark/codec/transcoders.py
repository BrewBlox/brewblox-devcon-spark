"""
Object-specific transcoders
"""


from abc import ABC, abstractclassmethod, abstractmethod
from enum import Enum
from typing import Generator, Optional, Tuple, Type, Union

from brewblox_service import brewblox_logger
from google.protobuf import json_format
from google.protobuf.message import Message
from google.protobuf.reflection import GeneratedProtocolMessageType

from . import pb2
from .opts import DecodeOpts, ProtoEnumOpt
from .processor import ProtobufProcessor

NumIdentifier_ = Tuple[int, int]
StrIdentifier_ = Tuple[str, Optional[str]]
Identifier_ = Union[NumIdentifier_, StrIdentifier_]


LOGGER = brewblox_logger(__name__)

BlockType = pb2.brewblox_pb2.BrewbloxTypes.BlockType
REQUEST_TYPE = 'ControlboxRequest'
RESPONSE_TYPE = 'ControlboxResponse'
REQUEST_TYPE_INT = -1
RESPONSE_TYPE_INT = -2


class Transcoder(ABC):

    def __init__(self, proc: ProtobufProcessor):
        self.proc = proc

    @abstractclassmethod
    def type_int(cls) -> int:
        """
        The numerical enum value for `objtype`
        """

    @abstractclassmethod
    def type_str(cls) -> str:
        """
        The string enum value for `objtype`.
        """

    @classmethod
    def subtype_int(cls) -> int:
        """
        Alternative messages must declare a `subtype` that is unique within `objtype`.
        """
        return 0

    @classmethod
    def subtype_str(cls) -> Optional[str]:
        """
        Alternative messages must declare a `subtype` that is unique within `objtype`.
        `subtype` itself is not an enum, so the name of the Protobuf message is used.
        Naturally, the Protobuf message name must also be unique within the namespace.

        If `subtype` is 0, the subtype name is None.
        This is applicable for the default Block messages.
        """
        return None

    @classmethod
    def type_impl(cls) -> list[str]:
        return []

    @abstractmethod
    def encode(self, values: dict) -> bytes:
        """
        Encode a Python dict to bytes.
        """

    @abstractmethod
    def decode(self, encoded: bytes, opts: DecodeOpts) -> dict:
        """
        Decode bytes to a Python dict.
        """

    @classmethod
    def get(cls, identifier: Identifier_, proc: ProtobufProcessor) -> 'Transcoder':
        objtype, subtype = identifier
        for trc in _TRANSCODERS:
            if objtype == trc.type_str() or objtype == trc.type_int():
                if subtype == trc.subtype_str() or subtype == trc.subtype_int():
                    return trc(proc)
        raise KeyError(f'No transcoder found for identifier {identifier}')


class BlockInterfaceTranscoder(Transcoder):

    @classmethod
    def type_int(cls) -> int:
        return cls._ENUM_VAL

    @classmethod
    def type_str(cls) -> str:
        return pb2.brewblox_pb2.BrewbloxTypes.BlockType.Name(cls._ENUM_VAL)

    def encode(self, values: dict) -> bytes:
        return b'\x00'

    def decode(self, values: bytes, _: DecodeOpts) -> dict:
        return dict()


class DeprecatedObjectTranscoder(Transcoder):

    @classmethod
    def type_int(cls) -> int:
        return 65533

    @classmethod
    def type_str(cls) -> str:
        return 'DeprecatedObject'

    def encode(self, values: dict) -> bytes:
        actual_id = values['actualId']
        encoded = actual_id.to_bytes(2, 'little')
        return encoded

    def decode(self, encoded: bytes, _: DecodeOpts) -> dict:
        actual_id = int.from_bytes(encoded, 'little')
        return {'actualId': actual_id}


class GroupsTranscoder(Transcoder):

    @classmethod
    def type_int(cls) -> int:
        return 65534

    @classmethod
    def type_str(cls) -> str:
        return 'Groups'

    def encode(self, values: dict) -> bytes:
        active = self.proc.pack_bit_flags(values.get('active', []))
        return active.to_bytes(1, 'little')

    def decode(self, encoded: bytes, _: DecodeOpts) -> dict:
        active = self.proc.unpack_bit_flags(int.from_bytes(encoded, 'little'))
        return {'active': active}


class BaseProtobufTranscoder(Transcoder):

    @classmethod
    def _brewblox_msg(cls):
        # Message opts as set in BrewbloxMessageOptions in brewblox.proto
        return cls._MESSAGE.DESCRIPTOR.GetOptions().Extensions[pb2.brewblox_pb2.brewblox_msg]

    @classmethod
    def type_int(cls) -> int:
        return cls._brewblox_msg().objtype

    @classmethod
    def type_str(cls) -> str:
        return BlockType.Name(cls.type_int())

    @classmethod
    def type_impl(cls) -> list[str]:
        return [BlockType.Name(i) for i in cls._brewblox_msg().impl]

    @classmethod
    def subtype_int(cls) -> int:
        return cls._brewblox_msg().subtype

    @classmethod
    def subtype_str(cls) -> Optional[str]:
        if cls.subtype_int():
            return cls._MESSAGE.DESCRIPTOR.name
        else:
            return None

    def create_message(self) -> Message:
        return self.__class__._MESSAGE()

    def encode(self, values: dict) -> bytes:
        # LOGGER.debug(f'encoding {values} to {self.__class__._MESSAGE}')
        obj = json_format.ParseDict(values, self.create_message())
        data = obj.SerializeToString()
        return data + b'\x00'  # Include null terminator

    def decode(self, encoded: bytes, opts: DecodeOpts) -> dict:
        # Remove null terminator
        encoded = encoded[:-1]
        int_enum = opts.enums == ProtoEnumOpt.INT

        obj = self.create_message()
        obj.ParseFromString(encoded)
        decoded = json_format.MessageToDict(
            message=obj,
            preserving_proto_field_name=True,
            including_default_value_fields=True,
            use_integers_for_enums=int_enum,
        )
        # LOGGER.debug(f'decoded {self.__class__._MESSAGE} to {decoded}')
        return decoded


class ControlboxRequestTranscoder(BaseProtobufTranscoder):
    _MESSAGE = pb2.brewblox_pb2.ControlboxRequest

    @classmethod
    def type_int(cls) -> int:
        return REQUEST_TYPE_INT  # never a payload

    @classmethod
    def type_str(cls) -> str:
        return REQUEST_TYPE

    def encode(self, values: dict) -> bytes:
        opcode = values.get('opcode')
        if isinstance(opcode, Enum):
            values['opcode'] = opcode.name
        return super().encode(values)


class ControlboxResponseTranscoder(BaseProtobufTranscoder):
    _MESSAGE = pb2.brewblox_pb2.ControlboxResponse

    @classmethod
    def type_int(cls) -> int:
        return RESPONSE_TYPE_INT  # never a payload

    @classmethod
    def type_str(cls) -> str:
        return RESPONSE_TYPE

    def encode(self, values: dict) -> bytes:
        error = values.get('error')
        if isinstance(error, Enum):
            values['error'] = error.name
        return super().encode(values)


class ProtobufTranscoder(BaseProtobufTranscoder):

    def encode(self, values: dict) -> bytes:
        self.proc.pre_encode(self.create_message(), values)
        return super().encode(values)

    def decode(self, encoded: bytes, opts: DecodeOpts) -> dict:
        decoded = super().decode(encoded, opts)
        self.proc.post_decode(self.create_message(), decoded, opts)
        return decoded


class EdgeCaseTranscoder(ProtobufTranscoder):
    _MESSAGE = pb2.EdgeCase_pb2.EdgeCase

    @classmethod
    def type_int(cls) -> int:
        return 9001

    @classmethod
    def type_str(cls) -> str:
        return 'EdgeCase'


class EdgeCaseSubTranscoder(EdgeCaseTranscoder):
    _MESSAGE = pb2.EdgeCase_pb2.SubCase


def interface_transcoder_generator() -> Generator[Type[BlockInterfaceTranscoder], None, None]:
    for objtype in BlockType.values():
        name = f'{BlockType.Name(objtype)}_InterfaceTranscoder'
        yield type(name, (BlockInterfaceTranscoder, ), {'_ENUM_VAL': objtype})


def protobuf_transcoder_generator() -> Generator[Type[ProtobufTranscoder], None, None]:
    for pb in [getattr(pb2, k) for k in pb2.__all__]:
        members = [getattr(pb, k)
                   for k in dir(pb)
                   if not k.startswith('_')]
        messages = [el
                    for el in members
                    if isinstance(el, GeneratedProtocolMessageType)]

        for msg in messages:
            desc = msg.DESCRIPTOR
            opts = desc.GetOptions().Extensions[pb2.brewblox_pb2.brewblox_msg]
            if opts.objtype:
                name = f'{BlockType.Name(opts.objtype)}_{desc.name}_Transcoder'
                yield type(name, (ProtobufTranscoder, ), {'_MESSAGE': msg})


_TRANSCODERS: list[Type[Transcoder]] = [
    # Raw system objects
    DeprecatedObjectTranscoder,
    GroupsTranscoder,
    ControlboxRequestTranscoder,
    ControlboxResponseTranscoder,

    # Protobuf objects
    *protobuf_transcoder_generator(),

    # Interface objects
    # These are fallbacks to be used if there is no direct object
    *interface_transcoder_generator(),

    # Debugging objects
    EdgeCaseTranscoder,
    EdgeCaseSubTranscoder,
]
