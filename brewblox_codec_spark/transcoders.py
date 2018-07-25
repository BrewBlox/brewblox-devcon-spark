"""
Object-specific transcoders
"""

from brewblox_codec_spark import _path_extension  # isort:skip

from abc import ABC, abstractclassmethod, abstractmethod
from typing import Iterable, Union

from brewblox_service import brewblox_logger
from google.protobuf import json_format
from google.protobuf.message import Message

import OneWireBus_pb2
import OneWireTempSensor_pb2
from brewblox_codec_spark.modifiers import Modifier

ObjType_ = Union[int, str]
Decoded_ = dict
Encoded_ = bytes

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

    def create_message(self) -> Message:
        return self.__class__._MESSAGE()

    def encode(self, values: Decoded_) -> Encoded_:
        LOGGER.debug(f'encoding {values} to {self.__class__._MESSAGE}')
        obj = json_format.ParseDict(values, self.create_message())
        data = obj.SerializeToString()
        return data + b'\x00'  # Include null terminator

    def decode(self, encoded: Encoded_) -> Decoded_:
        # Remove null terminator
        encoded = encoded[:-1]

        obj = self.create_message()
        obj.ParseFromString(encoded)
        decoded = json_format.MessageToDict(
            message=obj,
            preserving_proto_field_name=True,
            including_default_value_fields=True
        )
        LOGGER.debug(f'decoded {self.__class__._MESSAGE} to {decoded}')
        return decoded


class OptionsTranscoder(ProtobufTranscoder):

    def encode(self, values: Decoded_) -> Encoded_:
        self.mod.encode_options(self.create_message(), values)
        return super().encode(values)

    def decode(self, encoded: Encoded_) -> Decoded_:
        decoded = super().decode(encoded)
        self.mod.decode_options(self.create_message(), decoded)
        return decoded


class OneWireBusTranscoder(OptionsTranscoder):
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


class OneWireTempSensorTranscoder(OptionsTranscoder):
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
