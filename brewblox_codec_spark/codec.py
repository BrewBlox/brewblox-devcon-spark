"""
Generic entry point for all codecs.
Offers encoding and decoding of objects.
"""

import logging

from brewblox_codec_spark.proto import OneWireBus_pb2, OneWireTempSensor_pb2
from google.protobuf import json_format
from google.protobuf.internal import encoder as internal_encoder
from google.protobuf.internal import decoder as internal_decoder
from typing import Union

LOGGER = logging.getLogger(__name__)


_TYPE_MAPPING = {
    2: OneWireBus_pb2.OneWireCommand,
    3: OneWireBus_pb2.OneWireRead,
    6: OneWireTempSensor_pb2.OneWireTempSensor,
}


def encode_delimited(obj_type: int, values: dict) -> bytes:
    obj = _TYPE_MAPPING[obj_type]()
    obj = json_format.ParseDict(values, obj)

    data = obj.SerializeToString()
    delimiter = internal_encoder._VarintBytes(len(data))

    return delimiter + data


def decode_delimited(obj_type: int, encoded: Union[bytes, list]) -> dict:
    if isinstance(encoded, list):
        encoded = bytes(encoded)

    obj = _TYPE_MAPPING[obj_type]()

    (size, position) = internal_decoder._DecodeVarint(encoded, 0)
    obj.ParseFromString(encoded[position:position+size])

    return json_format.MessageToDict(obj)
