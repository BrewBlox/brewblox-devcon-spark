"""
Generic entry point for all codecs.
Offers encoding and decoding of objects.
"""

import logging
from abc import ABC, abstractmethod
from copy import deepcopy
from functools import wraps
from typing import Union, Any

from brewblox_codec_spark import path_extension
from brewblox_codec_spark.modifiers import (b64_to_hex, decode_quantity,
                                            encode_quantity, hex_to_b64,
                                            modify_if_present)
from brewblox_codec_spark.proto import OneWireBus_pb2, OneWireTempSensor_pb2
from google.protobuf import json_format
from google.protobuf.internal import decoder as internal_decoder
from google.protobuf.internal import encoder as internal_encoder
from google.protobuf.message import Message

LOGGER = logging.getLogger(__name__)


OBJ_TYPE_TYPE_ = Union[int, str]
ENCODE_DATA_TYPE_ = dict
DECODE_DATA_TYPE_ = Union[bytes, list]

# We import path_extension for its side effects
# "use" the import to avoid pep8 complaints
# Alternative (adding noqa mark), would also prevent IDE suggestions
LOGGER.debug(f'Extending path with {path_extension.PROTO_PATH}')


def encode(obj_type: OBJ_TYPE_TYPE_, values: ENCODE_DATA_TYPE_) -> bytes:
    assert isinstance(values, dict), f'Unable to encode [{type(values).__name__}] values'
    return _transcoder(obj_type).encode(values)


def decode(obj_type: OBJ_TYPE_TYPE_, encoded: DECODE_DATA_TYPE_) -> dict:
    assert isinstance(encoded, (bytes, list)), f'Unable to decode [{type(encoded).__name__}] values'
    return _transcoder(obj_type).decode(encoded)


def _transcoder(obj_type: str) -> 'Transcoder':
    try:
        return _TYPE_MAPPING[obj_type]()
    except KeyError:
        raise KeyError(f'No codec found for object type [{obj_type}]')


def copied_input(func):
    """
    Ensures input dict remains unchanged after pre-processing.
    This decorator can safely be used by multiple inheriting functions.
    It will only copy once.
    """
    @wraps(func)
    def lazy_copy(self, values: dict):
        safe_values = deepcopy(values)
        return func(self, safe_values)
    return lazy_copy


class Transcoder(ABC):

    @abstractmethod
    def encode(self, values: dict) -> bytes:
        pass

    @abstractmethod
    def decode(encoded: Any) -> dict:
        pass


class ProtobufTranscoder(Transcoder):

    @property
    def message(self) -> Message:
        return self.__class__._MESSAGE()

    @copied_input
    def encode(self, values: dict) -> bytes:
        LOGGER.debug(f'encoding {values} to {self.__class__._MESSAGE}')
        obj = json_format.ParseDict(values, self.message)
        data = obj.SerializeToString()

        # We're using delimited Protobuf messages
        # This means that messages are always prefixed with a varint indicating their encoded length
        delimiter = internal_encoder._VarintBytes(len(data))

        return delimiter + data

    def decode(self, encoded: Union[bytes, list]) -> dict:
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

    @copied_input
    def encode(self, values: dict) -> bytes:
        modified = encode_quantity(self.message, values)
        return super().encode(modified)

    def decode(self, encoded: Union[bytes, list]) -> dict:
        decoded = super().decode(encoded)
        decode_quantity(self.message, decoded)
        return decoded


class OneWireBusTranscoder(QuantifiedTranscoder):
    _MESSAGE = OneWireBus_pb2.OneWireBus

    @copied_input
    def encode(self, values: dict) -> bytes:
        modify_if_present(
            obj=values,
            path='/address',
            func=lambda addr: [hex_to_b64(a) for a in addr]
        )
        return super().encode(values)

    def decode(self, encoded: Union[bytes, list]) -> dict:
        decoded = super().decode(encoded)
        modify_if_present(
            obj=decoded,
            path='/address',
            func=lambda addr: [b64_to_hex(a) for a in addr]
        )
        return decoded


class OneWireTempSensorTranscoder(QuantifiedTranscoder):
    _MESSAGE = OneWireTempSensor_pb2.OneWireTempSensor

    @copied_input
    def encode(self, values: dict) -> bytes:
        modify_if_present(
            obj=values,
            path='/settings/address',
            func=hex_to_b64
        )
        return super().encode(values)

    def decode(self, encoded: Union[bytes, list]) -> dict:
        decoded = super().decode(encoded)
        modify_if_present(
            obj=decoded,
            path='/settings/address',
            func=b64_to_hex
        )
        return decoded


_TYPE_MAPPING = {
    0: OneWireBusTranscoder,
    10: OneWireBusTranscoder,
    6: OneWireTempSensorTranscoder,
}
