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


OBJ_TYPE_TYPE_ = Union[int, str]
ENCODE_DATA_TYPE_ = dict
DECODE_DATA_TYPE_ = Union[bytes, list]


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


def _modify_if_present(obj: dict, path: List[str], func: Callable, mutate_input: bool=False) -> dict:
    """
    Replaces a value in a (possibly nested) dict.
    Optionally first makes a deep copy of the input.

    If path is invalid, no values are changed.

    Example (not mutating input):
        >>> input = {'nested': { 'collection': { 'value': 0 }}}
        >>> output =_modify_if_present(
                        obj=input,
                        path=['nested', 'collection', 'value'],
                        func=lambda v: v +1,
                        mutate_input=False)
        >>> print(output)
        {'nested': { 'collection': { 'value': 1 }}}
        >>> print(input)
        {'nested': { 'collection': { 'value': 0 }}}

    Example (mutating input):
        >>> input = {'nested': { 'collection': { 'value': 0 }}}
        >>> output =_modify_if_present(
                        obj=input,
                        path=['nested', 'collection', 'value'],
                        func=lambda v: v +1,
                        mutate_input=True)
        >>> print(output)
        {'nested': { 'collection': { 'value': 1 }}}
        >>> print(input)
        {'nested': { 'collection': { 'value': 1 }}}

    """
    parent = deepcopy(obj) if not mutate_input else obj
    try:
        # `child` is a reference to a dict nested inside `parent`.
        # We move the `child` reference until it points to the dict containing the target value.
        # Any changes made to objects inside `child` can be observed in `parent`.
        child = parent
        for key in path[:-1]:
            child = child[key]

        # Update the value inside the `child` dict.
        # Because `parent` contains `child`, `parent` now also contains the modified value.
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
            mutate_input=False
        )
        return super().encode(modified)

    # Overrides
    def decode(self, *args, **kwargs) -> dict:
        decoded = super().decode(*args, **kwargs)
        return _modify_if_present(
            obj=decoded,
            path=['address'],
            func=lambda addr: [_b64_to_hex(a) for a in addr],
            mutate_input=True
        )


class OneWireTempSensorTranscoder(ProtobufTranscoder):
    _MESSAGE = OneWireTempSensor_pb2.OneWireTempSensor

    # Overrides
    def encode(self, values: dict) -> bytes:
        modified = _modify_if_present(
            obj=values,
            path=['settings', 'address'],
            func=_hex_to_b64,
            mutate_input=False
        )
        return super().encode(modified)

    # Overrides
    def decode(self, *args, **kwargs) -> dict:
        decoded = super().decode(*args, **kwargs)
        return _modify_if_present(
            obj=decoded,
            path=['settings', 'address'],
            func=_b64_to_hex,
            mutate_input=True
        )


_TYPE_MAPPING = {
    0: OneWireBusTranscoder,
    10: OneWireBusTranscoder,
    6: OneWireTempSensorTranscoder,
}
