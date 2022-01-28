"""
Object-specific transcoders
"""

from abc import ABC, abstractclassmethod, abstractmethod
from collections import defaultdict
from typing import Generator, Type, Union

from brewblox_service import brewblox_logger
from google.protobuf import json_format
from google.protobuf.message import Message
from google.protobuf.reflection import GeneratedProtocolMessageType

from . import pb2
from .modifiers import Modifier
from .opts import DecodeOpts, ProtoEnumOpt

ObjType_ = Union[int, str]
Decoded_ = dict
Encoded_ = bytes

LOGGER = brewblox_logger(__name__)

BlockType = pb2.brewblox_pb2.BlockType


class Transcoder(ABC):

    def __init__(self, mods: Modifier):
        self.mod = mods

    @abstractclassmethod
    def type_int(cls) -> int:
        pass  # pragma: no cover

    @abstractclassmethod
    def type_str(cls) -> str:
        pass  # pragma: no cover

    @classmethod
    def type_impl(cls) -> list[int]:
        return []

    @abstractmethod
    def encode(self, values: Decoded_) -> Encoded_:
        pass  # pragma: no cover

    @abstractmethod
    def decode(self, encoded: Encoded_, opts: DecodeOpts) -> Decoded_:
        pass  # pragma: no cover

    @classmethod
    def get(cls, obj_type: ObjType_, mods: Modifier) -> 'Transcoder':
        for trc in _TRANSCODERS:
            if obj_type == trc.type_str() or obj_type == trc.type_int():
                return trc(mods)
        raise KeyError(f'No transcoder found for identifier {obj_type}')

    @classmethod
    def type_tree(cls, mods: Modifier) -> dict[str, list[str]]:
        impl_tree = defaultdict(list)
        for trc in _TRANSCODERS:
            name = trc.type_str()
            for intf in [Transcoder.get(t, mods).type_str() for t in trc.type_impl()]:
                impl_tree[intf].append(name)
        return impl_tree


class BlockInterfaceTranscoder(Transcoder):

    @classmethod
    def type_int(cls) -> int:
        return cls._ENUM_VAL

    @classmethod
    def type_str(cls) -> str:
        return BlockType.Name(cls._ENUM_VAL)

    def encode(self, values: Decoded_) -> Encoded_:
        return b'\x00'

    def decode(self, values: Encoded_, _: DecodeOpts) -> Decoded_:
        return dict()


class InactiveObjectTranscoder(Transcoder):

    @classmethod
    def type_int(cls) -> int:
        return 65535

    @classmethod
    def type_str(cls) -> str:
        return 'InactiveObject'

    def encode(self, values: Decoded_) -> Encoded_:
        type_id = values['actualType']
        encoded = Transcoder.get(type_id, self.mod).type_int().to_bytes(2, 'little')
        return encoded

    def decode(self, encoded: Encoded_, _: DecodeOpts) -> Decoded_:
        type_id = int.from_bytes(encoded, 'little')
        return {'actualType': Transcoder.get(type_id, self.mod).type_str()}


class DeprecatedObjectTranscoder(Transcoder):

    @classmethod
    def type_int(cls) -> int:
        return 65533

    @classmethod
    def type_str(cls) -> str:
        return 'DeprecatedObject'

    def encode(self, values: Decoded_) -> Encoded_:
        actual_id = values['actualId']
        encoded = actual_id.to_bytes(2, 'little')
        return encoded

    def decode(self, encoded: Encoded_, _: DecodeOpts) -> Decoded_:
        actual_id = int.from_bytes(encoded, 'little')
        return {'actualId': actual_id}


class GroupsTranscoder(Transcoder):

    @classmethod
    def type_int(cls) -> int:
        return 65534

    @classmethod
    def type_str(cls) -> str:
        return 'Groups'

    def encode(self, values: Decoded_) -> Encoded_:
        active = self.mod.pack_bit_flags(values.get('active', []))
        return active.to_bytes(1, 'little')

    def decode(self, encoded: Encoded_, _: DecodeOpts) -> Decoded_:
        active = self.mod.unpack_bit_flags(int.from_bytes(encoded, 'little'))
        return {'active': active}


class BaseProtobufTranscoder(Transcoder):

    @classmethod
    def _brewblox_msg(cls):
        # Message opts as set in BrewbloxMessageOptions in brewblox.proto
        return cls._MESSAGE.DESCRIPTOR.GetOptions().Extensions[pb2.brewblox_pb2.msg]

    @classmethod
    def type_int(cls) -> int:
        return cls._brewblox_msg().objtype

    @classmethod
    def type_str(cls) -> str:
        return BlockType.Name(cls.type_int())

    @classmethod
    def type_impl(cls) -> list[str]:
        return [BlockType.Name(i) for i in cls._brewblox_msg().impl]

    def create_message(self) -> Message:
        return self.__class__._MESSAGE()

    def encode(self, values: Decoded_) -> Encoded_:
        # LOGGER.debug(f'encoding {values} to {self.__class__._MESSAGE}')
        obj = json_format.ParseDict(values, self.create_message())
        data = obj.SerializeToString()
        return data + b'\x00'  # Include null terminator

    def decode(self, encoded: Encoded_, opts: DecodeOpts) -> Decoded_:
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


class ProtobufTranscoder(BaseProtobufTranscoder):

    def encode(self, values: Decoded_) -> Encoded_:
        self.mod.encode_options(self.create_message(), values)
        return super().encode(values)

    def decode(self, encoded: Encoded_, opts: DecodeOpts) -> Decoded_:
        decoded = super().decode(encoded, opts)
        self.mod.decode_options(self.create_message(), decoded, opts)
        return decoded


class EdgeCaseTranscoder(ProtobufTranscoder):
    _MESSAGE = pb2.EdgeCase_pb2.Block

    @classmethod
    def type_int(cls) -> int:
        return 9001

    @classmethod
    def type_str(cls) -> str:
        return 'EdgeCase'


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
            opts = desc.GetOptions().Extensions[pb2.brewblox_pb2.msg]
            if opts.objtype:
                name = f'{BlockType.Name(opts.objtype)}_{desc.name}_Transcoder'
                yield type(name, (ProtobufTranscoder, ), {'_MESSAGE': msg})


_TRANSCODERS: list[Type[Transcoder]] = [
    # Raw system objects
    InactiveObjectTranscoder,
    DeprecatedObjectTranscoder,
    GroupsTranscoder,

    # Protobuf objects
    *protobuf_transcoder_generator(),

    # Interface objects
    # These are fallbacks to be used if there is no direct object
    *interface_transcoder_generator(),

    # Debugging objects
    EdgeCaseTranscoder,
]
