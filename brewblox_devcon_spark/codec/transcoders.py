"""
Object-specific transcoders
"""

from brewblox_devcon_spark.codec import _path_extension  # isort:skip

from abc import ABC, abstractclassmethod, abstractmethod
from typing import Iterable, Union

import ActuatorAnalogMock_pb2
import ActuatorDS2413_pb2
import ActuatorOffset_pb2
import ActuatorPin_pb2
import ActuatorPwm_pb2
import Balancer_pb2
import brewblox_pb2
import DisplaySettings_pb2
import DS2413_pb2
import EdgeCase_pb2
import Mutex_pb2
import OneWireBus_pb2
import Pid_pb2
import SetpointProfile_pb2
import SetpointSensorPair_pb2
import SysInfo_pb2
import TempSensorMock_pb2
import TempSensorOneWire_pb2
import Ticks_pb2
import TouchSettings_pb2
import WiFiSettings_pb2
from brewblox_devcon_spark.codec.modifiers import Modifier
from brewblox_service import brewblox_logger
from google.protobuf import json_format
from google.protobuf.message import Message

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
    def encode(self, values: Decoded_, opts: dict) -> Encoded_:
        pass  # pragma: no cover

    @abstractmethod
    def decode(encoded: Encoded_, opts: dict) -> Decoded_:
        pass  # pragma: no cover

    @classmethod
    def get(cls, obj_type: ObjType_, mods: Modifier) -> 'Transcoder':
        try:
            return _TYPE_MAPPING[obj_type](mods)
        except KeyError:
            raise KeyError(f'No codec found for object type [{obj_type}]')


class BlockInterfaceTranscoder(Transcoder):

    @classmethod
    def type_int(cls) -> int:
        return cls._ENUM_VAL

    @classmethod
    def type_str(cls) -> str:
        return brewblox_pb2.BrewbloxOptions.BlockType.Name(cls._ENUM_VAL)

    def encode(self, values: Decoded_, _) -> Encoded_:
        return b'\x00'

    def decode(self, values: Encoded_, _) -> Decoded_:
        return dict()


def interface_factory(value: int) -> BlockInterfaceTranscoder:
    name = f'{brewblox_pb2.BrewbloxOptions.BlockType.Name(value)}TranscoderStub'
    return type(name, (BlockInterfaceTranscoder, ), {'_ENUM_VAL': value})


class InactiveObjectTranscoder(Transcoder):

    @classmethod
    def type_int(cls) -> int:
        return 65535

    @classmethod
    def type_str(cls) -> str:
        return 'InactiveObject'

    def encode(self, values: Decoded_, _) -> Encoded_:
        type_id = values['actualType']
        encoded = Transcoder.get(type_id, self.mod).type_int().to_bytes(2, 'little')
        return encoded

    def decode(self, encoded: Encoded_, _) -> Decoded_:
        type_id = int.from_bytes(encoded, 'little')
        return {'actualType': Transcoder.get(type_id, self.mod).type_str()}


class GroupsTranscoder(Transcoder):

    @classmethod
    def type_int(cls) -> int:
        return 65534

    @classmethod
    def type_str(cls) -> str:
        return 'Groups'

    def encode(self, values: Decoded_, _) -> Encoded_:
        active = self.mod.pack_bit_flags(values.get('active', []))
        return active.to_bytes(1, 'little')

    def decode(self, encoded: Encoded_, _) -> Decoded_:
        active = self.mod.unpack_bit_flags(int.from_bytes(encoded, 'little'))
        return {'active': active}


class ProtobufTranscoder(Transcoder):

    @classmethod
    def type_int(cls) -> int:
        return cls._MESSAGE.DESCRIPTOR.GetOptions().Extensions[brewblox_pb2.brewblox_msg].objtype

    @classmethod
    def type_str(cls) -> str:
        return cls._MESSAGE.__name__

    def create_message(self) -> Message:
        return self.__class__._MESSAGE()

    def encode(self, values: Decoded_, _) -> Encoded_:
        # LOGGER.debug(f'encoding {values} to {self.__class__._MESSAGE}')
        obj = json_format.ParseDict(values, self.create_message())
        data = obj.SerializeToString()
        return data + b'\x00'  # Include null terminator

    def decode(self, encoded: Encoded_, _) -> Decoded_:
        # Remove null terminator
        encoded = encoded[:-1]

        obj = self.create_message()
        obj.ParseFromString(encoded)
        decoded = json_format.MessageToDict(
            message=obj,
            preserving_proto_field_name=True,
            including_default_value_fields=True,
            use_integers_for_enums=True,
        )
        # LOGGER.debug(f'decoded {self.__class__._MESSAGE} to {decoded}')
        return decoded


class OptionsTranscoder(ProtobufTranscoder):

    def encode(self, values: Decoded_, opts: dict) -> Encoded_:
        self.mod.encode_options(self.create_message(), values, opts)
        return super().encode(values, opts)

    def decode(self, encoded: Encoded_, opts: dict) -> Decoded_:
        decoded = super().decode(encoded, opts)
        self.mod.decode_options(self.create_message(), decoded, opts)
        return decoded


class EdgeCaseTranscoder(OptionsTranscoder):
    _MESSAGE = EdgeCase_pb2.EdgeCase

    @classmethod
    def type_int(cls) -> int:
        return 9001

    @classmethod
    def type_str(cls) -> str:
        return 'EdgeCase'


def options_type_factory(message):
    name = f'{message.__name__}Transcoder'
    return type(name, (OptionsTranscoder, ), {'_MESSAGE': message})


def _generate_mapping(vals: Iterable[Transcoder]):
    for trc in vals:
        yield trc.type_int(), trc
        yield trc.type_str(), trc


_TRANSCODERS = [
    # Raw system objects
    InactiveObjectTranscoder,
    GroupsTranscoder,

    # Interface objects
    # Actual implementations will override this later
    *[interface_factory(v) for v in brewblox_pb2.BrewbloxOptions.BlockType.values()],

    # Protobuf objects
    *[options_type_factory(msg) for msg in [
        ActuatorAnalogMock_pb2.ActuatorAnalogMock,
        ActuatorDS2413_pb2.ActuatorDS2413,
        ActuatorOffset_pb2.ActuatorOffset,
        ActuatorPin_pb2.ActuatorPin,
        ActuatorPwm_pb2.ActuatorPwm,
        Balancer_pb2.Balancer,
        DisplaySettings_pb2.DisplaySettings,
        DS2413_pb2.DS2413,
        Mutex_pb2.Mutex,
        OneWireBus_pb2.OneWireBus,
        Pid_pb2.Pid,
        SetpointProfile_pb2.SetpointProfile,
        SetpointSensorPair_pb2.SetpointSensorPair,
        SysInfo_pb2.SysInfo,
        TempSensorMock_pb2.TempSensorMock,
        TempSensorOneWire_pb2.TempSensorOneWire,
        Ticks_pb2.Ticks,
        TouchSettings_pb2.TouchSettings,
        WiFiSettings_pb2.WiFiSettings,
    ]],

    # Debugging object
    EdgeCaseTranscoder,
]

_TYPE_MAPPING = {k: v for k, v in _generate_mapping(_TRANSCODERS)}
