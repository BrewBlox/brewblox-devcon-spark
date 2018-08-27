"""
Object-specific transcoders
"""

from brewblox_devcon_spark.codec import _path_extension  # isort:skip

from abc import ABC, abstractclassmethod, abstractmethod
from typing import Iterable, Union

from brewblox_service import brewblox_logger
from google.protobuf import json_format
from google.protobuf.message import Message

import EdgeCase_pb2
import OneWireBus_pb2
import OneWireTempSensor_pb2
import Pid_pb2
import SensorSetPointPair_pb2
import SetPointSimple_pb2
import SysInfo_pb2
import Ticks_pb2
import XboxController_pb2
from brewblox_devcon_spark.codec.modifiers import Modifier

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
        pass  # pragma: no cover

    @abstractclassmethod
    def type_str(cls) -> str:
        pass  # pragma: no cover

    @abstractmethod
    def encode(self, values: Decoded_) -> Encoded_:
        pass  # pragma: no cover

    @abstractmethod
    def decode(encoded: Encoded_) -> Decoded_:
        pass  # pragma: no cover

    @classmethod
    def get(cls, obj_type: ObjType_, mods: Modifier) -> 'Transcoder':
        try:
            return _TYPE_MAPPING[obj_type](mods)
        except KeyError:
            raise KeyError(f'No codec found for object type [{obj_type}]')


class InactiveObjectTranscoder(Transcoder):

    @classmethod
    def type_int(cls) -> int:
        return 1

    @classmethod
    def type_str(cls) -> str:
        return 'InactiveObject'

    def encode(self, values: Decoded_) -> Encoded_:
        type_id = values['actualType']
        encoded = Transcoder.get(type_id, self.mod).type_int().to_bytes(2, 'little')
        return encoded

    def decode(self, encoded: Encoded_) -> Decoded_:
        type_id = int.from_bytes(encoded, 'little')
        return {'actualType': Transcoder.get(type_id, self.mod).type_str()}


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


class OneWireTempSensorTranscoder(OptionsTranscoder):
    _MESSAGE = OneWireTempSensor_pb2.OneWireTempSensor
    _TYPE_INT = 257


class PidTranscoder(OptionsTranscoder):
    _MESSAGE = Pid_pb2.Pid
    _TYPE_INT = 258


class SensorSetPointPairTranscoder(OptionsTranscoder):
    _MESSAGE = SensorSetPointPair_pb2.SensorSetPointPair
    _TYPE_INT = 259


class SetPointSimpleTranscoder(OptionsTranscoder):
    _MESSAGE = SetPointSimple_pb2.SetPointSimple
    _TYPE_INT = 260


class TicksTranscoder(OptionsTranscoder):
    _MESSAGE = Ticks_pb2.Ticks
    _TYPE_INT = 262


class ProfilesTranscoder(Transcoder):
    @classmethod
    def type_int(cls) -> int:
        return 2

    @classmethod
    def type_str(cls) -> str:
        return 'Profiles'

    def encode(self, values: Decoded_) -> Encoded_:
        active = self.mod.pack_bit_flags(values.get('active', []))
        return active.to_bytes(1, 'little')

    def decode(self, encoded: Encoded_) -> Decoded_:
        active = self.mod.unpack_bit_flags(int.from_bytes(encoded, 'little'))
        return {'active': active}


class SysInfoTranscoder(OptionsTranscoder):
    _MESSAGE = SysInfo_pb2.SysInfo
    _TYPE_INT = 264


class EdgeCaseTranscoder(OptionsTranscoder):
    _MESSAGE = EdgeCase_pb2.EdgeCase
    _TYPE_INT = 9001


class XboxControllerTranscoder(OptionsTranscoder):
    _MESSAGE = XboxController_pb2.XboxController
    _TYPE_INT = 9002


def _generate_mapping(vals: Iterable[Transcoder]):
    for trc in vals:
        yield trc.type_int(), trc
        yield trc.type_str(), trc


_TRANSCODERS = [
    InactiveObjectTranscoder,
    OneWireBusTranscoder,
    OneWireTempSensorTranscoder,
    SetPointSimpleTranscoder,
    SensorSetPointPairTranscoder,
    PidTranscoder,
    ProfilesTranscoder,
    SysInfoTranscoder,
    TicksTranscoder,

    # Debug/testing transcoders
    EdgeCaseTranscoder,
    XboxControllerTranscoder,
]

_TYPE_MAPPING = {k: v for k, v in _generate_mapping(_TRANSCODERS)}
