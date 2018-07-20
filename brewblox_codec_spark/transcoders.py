"""
Object-specific transcoders
"""

from brewblox_codec_spark import _path_extension  # isort:skip

from abc import ABC, abstractclassmethod, abstractmethod
from typing import Iterable, Union

from brewblox_service import brewblox_logger
from google.protobuf import json_format
from google.protobuf.internal import decoder as internal_decoder
from google.protobuf.internal import encoder as internal_encoder
from google.protobuf.message import Message

import OneWireBus_pb2
import OneWireTempSensor_pb2
from brewblox_codec_spark.modifiers import Modifier

ObjType_ = Union[int, str]
Decoded_ = dict
Encoded_ = Union[bytes, list]

_path_extension.avoid_lint_errors()
LOGGER = brewblox_logger(__name__)


class Transcoder(ABC):

    def __init__(self, mods: Modifier):
        self.mod = mods

    @abstractclassmethod
    def type_int(cls) -> int:
        pass

    @abstractclassmethod
    def type_str(cls) -> str:
        pass

    @abstractmethod
    def encode(self, values: Decoded_) -> Encoded_:
        pass

    @abstractmethod
    def decode(encoded: Encoded_) -> Decoded_:
        pass

    @classmethod
    def get(cls, obj_type: ObjType_, mods: Modifier) -> 'Transcoder':
        try:
            return _TYPE_MAPPING[obj_type](mods)
        except KeyError:
            raise KeyError(f'No codec found for object type [{obj_type}]')


class ProtobufTranscoder(Transcoder):

    @classmethod
    def type_int(cls) -> int:
        return cls._TYPE_INT

    @classmethod
    def type_str(cls) -> str:
        return cls._MESSAGE.__name__

    @property
    def message(self) -> Message:
        return self.__class__._MESSAGE()

    def encode(self, values: Decoded_) -> Encoded_:
        LOGGER.debug(f'encoding {values} to {self.__class__._MESSAGE}')
        obj = json_format.ParseDict(values, self.message)
        data = obj.SerializeToString()

        # We're using delimited Protobuf messages
        # This means that messages are always prefixed with a varint indicating their encoded length
        delimiter = internal_encoder._VarintBytes(len(data))

        return delimiter + data

    def decode(self, encoded: Encoded_) -> Decoded_:
        # Supports binary input as both a byte string, or as a list of ints
        if isinstance(encoded, list):
            encoded = bytes(encoded)

        obj = self.message
        # We're using delimited Protobuf messages
        # This means that messages are always prefixed with a varint indicating their encoded length
        # This is not strictly part of the Protobuf spec, so we need to slice it off before parsing
        (size, position) = internal_decoder._DecodeVarint(encoded, 0)
        obj.ParseFromString(encoded[position:position+size])

        decoded = json_format.MessageToDict(obj)
        LOGGER.debug(f'decoded {self.__class__._MESSAGE} to {decoded}')
        return decoded


class QuantifiedTranscoder(ProtobufTranscoder):

    def encode(self, values: Decoded_) -> Encoded_:
        self.mod.encode_quantity(self.message, values)
        return super().encode(values)

    def decode(self, encoded: Encoded_) -> Decoded_:
        decoded = super().decode(encoded)
        self.mod.decode_quantity(self.message, decoded)
        return decoded


class OneWireBusTranscoder(QuantifiedTranscoder):
    _MESSAGE = OneWireBus_pb2.OneWireBus
    _TYPE_INT = 256

    def encode(self, values: Decoded_) -> Encoded_:
        self.mod.modify_if_present(
            obj=values,
            path='/address',
            func=lambda addr: [self.mod.hex_to_b64(a) for a in addr]
        )
        return super().encode(values)

    def decode(self, encoded: Encoded_) -> Decoded_:
        decoded = super().decode(encoded)
        self.mod.modify_if_present(
            obj=decoded,
            path='/address',
            func=lambda addr: [self.mod.b64_to_hex(a) for a in addr]
        )
        return decoded


class OneWireTempSensorTranscoder(QuantifiedTranscoder):
    _MESSAGE = OneWireTempSensor_pb2.OneWireTempSensor
    _TYPE_INT = 257

    def encode(self, values: Decoded_) -> Encoded_:
        self.mod.modify_if_present(
            obj=values,
            path='/settings/address',
            func=self.mod.hex_to_b64
        )
        return super().encode(values)

    def decode(self, encoded: Encoded_) -> Decoded_:
        decoded = super().decode(encoded)
        self.mod.modify_if_present(
            obj=decoded,
            path='/settings/address',
            func=self.mod.b64_to_hex
        )
        return decoded


def _generate_mapping(vals: Iterable[Transcoder]):
    for trc in vals:
        yield trc.type_int(), trc
        yield trc.type_str(), trc


_TRANSCODERS = [
    OneWireBusTranscoder,
    OneWireTempSensorTranscoder
]

_TYPE_MAPPING = {k: v for k, v in _generate_mapping(_TRANSCODERS)}
