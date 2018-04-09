"""
Generic entry point for all codecs.
Offers encoding and decoding of objects.
"""

import logging
from abc import ABC, abstractmethod
from base64 import b64decode, b64encode
from binascii import hexlify, unhexlify
from copy import deepcopy
from typing import Callable, List, Union

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


def _modify_if_present(obj: dict, path: List[str], func: Callable, copy: bool=True) -> dict:
    """
    Replaces a value in a (possibly nested) dict.
    Optionally first makes a deep copy of the input.

    If path is invalid, no values are changed.
    """
    parent = deepcopy(obj) if copy else obj
    try:
        child = parent
        for key in path[:-1]:
            child = child[key]

        child[path[-1]] = func(child[path[-1]])

    except KeyError:
        pass

    return parent


def _hex_to_b64(s):
    return b64encode(unhexlify(s)).decode()


def _b64_to_hex(s):
    return hexlify(b64decode(s)).decode()


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


class OneWireBusTranscoder(ProtobufTranscoder):
    _MESSAGE = OneWireBus_pb2.OneWireBus

    # Overrides
    def encode(self, values: dict) -> bytes:
        modified = _modify_if_present(
            obj=values,
            path=['address'],
            func=lambda addr: [_hex_to_b64(a) for a in addr],
            copy=True
        )
        return super().encode(modified)

    # Overrides
    def decode(self, *args, **kwargs) -> dict:
        decoded = super().decode(*args, **kwargs)
        return _modify_if_present(
            obj=decoded,
            path=['address'],
            func=lambda addr: [_b64_to_hex(a) for a in addr],
            copy=False
        )


class OneWireTempSensorTranscoder(ProtobufTranscoder):
    _MESSAGE = OneWireTempSensor_pb2.OneWireTempSensor

    # Overrides
    def encode(self, values: dict) -> bytes:
        modified = _modify_if_present(
            obj=values,
            path=['settings', 'address'],
            func=_hex_to_b64,
            copy=True
        )
        return super().encode(modified)

    # Overrides
    def decode(self, *args, **kwargs) -> dict:
        decoded = super().decode(*args, **kwargs)
        return _modify_if_present(
            obj=decoded,
            path=['settings', 'address'],
            func=_b64_to_hex,
            copy=False
        )


_TYPE_MAPPING = {
    0: OneWireBusTranscoder,
    10: OneWireBusTranscoder,
    6: OneWireTempSensorTranscoder,
}
