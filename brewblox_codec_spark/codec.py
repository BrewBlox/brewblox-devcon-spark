"""
Generic entry point for all codecs.
Offers encoding and decoding of objects.
"""

import logging
from abc import ABC, abstractmethod
from typing import Union
from binascii import hexlify

from brewblox_codec_spark.proto import OneWireBus_pb2, OneWireTempSensor_pb2
from google.protobuf import json_format
from google.protobuf.internal import decoder as internal_decoder
from google.protobuf.internal import encoder as internal_encoder

LOGGER = logging.getLogger(__name__)


def encode(obj_type: int, values: dict) -> bytes:
    return _transcoder(obj_type).encode(values)


def decode(obj_type: int, encoded: Union[bytes, list]) -> dict:
    return _transcoder(obj_type).decode(encoded)


def _transcoder(obj_type: str) -> 'Transcoder':
    try:
        return _TYPE_MAPPING[obj_type]()
    except KeyError:
        raise KeyError(f'No codec found for object type [{obj_type}]')


class Transcoder(ABC):

    @abstractmethod
    def encode(self, values: dict) -> bytes:
        pass

    @abstractmethod
    def decode(encoded: Union[bytes, list]) -> dict:
        pass


class ProtobufTranscoder(Transcoder):

    @property
    def message(self):
        return self.__class__._MESSAGE()

    def encode(self, values: dict) -> bytes:
        obj = json_format.ParseDict(values, self.message)

        data = obj.SerializeToString()

        # We're using delimited Protobuf messages
        # This means that messages are always prefixed with a varint indicating their encoded length
        delimiter = internal_encoder._VarintBytes(len(data))

        encoded = delimiter + data
        LOGGER.info(f'Encoded {self.message.__class__} as {hexlify(encoded)}')
        return encoded

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

        return json_format.MessageToDict(obj)


class OneWireBusTranscoder(ProtobufTranscoder):
    _MESSAGE = OneWireBus_pb2.OneWireBus


class OneWireTempSensorTranscoder(ProtobufTranscoder):
    _MESSAGE = OneWireTempSensor_pb2.OneWireTempSensor


_TYPE_MAPPING = {
    10: OneWireBusTranscoder,
    6: OneWireTempSensorTranscoder,
}
