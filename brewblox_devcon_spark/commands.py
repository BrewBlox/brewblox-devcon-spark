"""
Definitions for all commands that can be sent to the Spark.

The Command base class offers the functionality to convert dicts to and from byte strings,
based on the defined construct Struct.

Each child class of Command defines how the syntax for itself looks like.
"""

from abc import ABC
from binascii import hexlify, unhexlify
from functools import reduce
from typing import List

from brewblox_service import brewblox_logger
from construct import (Adapter, Byte, Const, Container, Default, Enum,
                       GreedyBytes, Int8sb, Int16ub, Struct)

LOGGER = brewblox_logger(__name__)

HexStr_ = str


VALUE_SEPARATOR = ','

OBJECT_ID_KEY = 'object_id'
SYSTEM_ID_KEY = 'system_object_id'
OBJECT_TYPE_KEY = 'object_type'
OBJECT_DATA_KEY = 'object_data'
OBJECT_LIST_KEY = 'objects'
PROFILE_LIST_KEY = 'profiles'


OpcodeEnum = Enum(Byte,
                  READ_OBJECT=1,
                  WRITE_OBJECT=2,
                  CREATE_OBJECT=3,
                  DELETE_OBJECT=4,
                  READ_SYSTEM_OBJECT=5,
                  WRITE_SYSTEM_OBJECT=6,
                  READ_ACTIVE_PROFILES=7,
                  WRITE_ACTIVE_PROFILES=8,
                  LIST_ACTIVE_OBJECTS=9,
                  LIST_SAVED_OBJECTS=10,
                  LIST_SYSTEM_OBJECTS=11,
                  CLEAR_PROFILE=12,
                  FACTORY_RESET=13,
                  RESTART=14,
                  )

ErrorcodeEnum = Enum(Int8sb,
                     OK=0,
                     UNKNOWN_ERROR=-1,
                     STREAM_ERROR=-2,
                     PROFILE_NOT_ACTIVE=-3,
                     INSUFFICIENT_PERSISTENT_STORAGE=-16,
                     INSUFFICIENT_HEAP=-17,

                     OBJECT_NOT_WRITABLE=-32,
                     OBJECT_NOT_READABLE=-33,
                     OBJECT_NOT_CREATABLE=-34,
                     OBJECT_NOT_DELETABLE=-35,
                     OBJECT_NOT_CONTAINER=-37,
                     CONTAINER_FULL=-38,

                     INVALID_PARAMETER=-64,
                     INVALID_OBJECT_ID=-65,
                     INVALID_TYPE=-66,
                     INVALID_SIZE=-67,
                     INVALID_PROFILE=-68,
                     INVALID_ID=-69
                     )


class ProfileListAdapter(Adapter):
    def __init__(self):
        super().__init__(Byte)

    def _encode(self, obj: List[int], context, path) -> int:
        if next((i for i in obj if i >= 8), None):
            raise ValueError(f'Invalid profile(s) in {obj}. Values must be 0-7.')
        return reduce(lambda result, idx: result | 1 << idx, obj, 0)

    def _decode(self, obj: int, context, path) -> List[int]:
        return [i for i in range(8) if 1 << i & obj]


class CommandException(Exception):
    pass


class Command(ABC):
    """
    Base class for all commands.
    This class handles encoding and decoding of arguments.

    Subclasses are expected to set static class variables to define their protocol.
    The constructor will fail if these are not defined.

    Required class variables:
        _OPCODE: OpcodeEnum
        _REQUEST: Struct
        _RESPONSE: Struct
        _VALUES: Tuple[str, Struct]

    _OPCODE must always be set, _REQUEST, _RESPONSE, and _VALUES can be None.

    _REQUEST or _RESPONSE being None does not mean the controller will literally send or receive nothing.
    opcode is always sent, and errcode is always received.

    _VALUES must be formatted as Tuple[str, Struct]. The string indicates the key in the decoded response.

    Example:

        class ExampleCommand(Command):
            _OPCODE = OpcodeEnum.UNUSED
            _REQUEST = Struct('first_arg' / Int8sb) + Struct('second_arg' / Int8sb)
            _RESPONSE = None
            _VALUES = ('response_list', Int8sb)

        decoded = {
            'first_arg': 1,
            'second_arg': 2,
            'response_list': [4, 5, 6]
        }
    """

    def __init__(self, encoded=(None, None), decoded=(None, None)):
        self._encoded_request, self._encoded_response = encoded
        self._decoded_request, self._decoded_response = decoded

        self._check_sanity()

        # `opcode` is defined as a private variable in request.
        # it will be included in `self.encoded_request`, but not in `self.decoded_request`.
        # `opcode` values are linked to the class, and will never deviate from the class-defined value.
        opcode_val = self.__class__._OPCODE
        opcode = Struct('_opcode' / Const(OpcodeEnum.encmapping[opcode_val], Byte))

        # `errcode` is defined as a private variable in response.
        # It will be included in `self.encoded_response`, but not in `self.decoded_response`.
        # `errcode` value is linked to the call, but defaults to OK when calling `Command.from_decoded()`.
        # When decoding, errors will be converted to Python exceptions
        errcode = Struct('_errcode' / Default(ErrorcodeEnum, ErrorcodeEnum.OK))

        request = self.__class__._REQUEST or Struct()
        self._request = opcode + request

        response = self.__class__._RESPONSE or Struct()
        self._response = errcode + response

        values = self.__class__._VALUES or (None, None)
        self._values_key = values[0]
        self._values_type = values[1]

    def _check_sanity(self):
        # Croak on accidental calls to `Command().from_args()`
        if all([
            self._encoded_request is None,
            self._encoded_response is None,
            self._decoded_request is None,
            self._decoded_response is None,
        ]):
            raise ValueError('Command has neither encoded or decoded values')

        # self.decoded_response() short-circuit returns self._decoded_response, regardless of _errorcode value
        # Constructing commands from decoded values is already an edge case.
        # Calling from_decoded() with an active error would be an edge case of an edge case.
        # Verdict: just don't do it.
        if '_errcode' in (self._decoded_response or {}):
            raise NotImplementedError('Creating a decoded command with an active error is not supported')

    def __str__(self):
        return f'<{type(self).__name__} [{self.name}]>'

    @classmethod
    def from_args(cls, **kwargs) -> 'Command':
        cmd = cls(decoded=(kwargs, None))
        LOGGER.debug(f'{cmd} from args: {kwargs}')
        return cmd

    @classmethod
    def from_encoded(cls, request: str=None, response: str=None) -> 'Command':
        cmd = cls(encoded=(request, response))
        LOGGER.debug(f'{cmd} from encoded: {request} | {response}')
        return cmd

    @classmethod
    def from_decoded(cls, request: dict=None, response: dict=None) -> 'Command':
        cmd = cls(decoded=(request, response))
        LOGGER.debug(f'{cmd} from decoded: {request} | {response}')
        return cmd

    @property
    def name(self) -> str:
        return str(self.__class__._OPCODE)

    @property
    def request(self) -> Struct:
        return self._request

    @property
    def response(self) -> Struct:
        return self._response

    @property
    def values_key(self) -> str:
        return self._values_key

    @property
    def values(self) -> Struct:
        return self._values_type

    @property
    def encoded_request(self) -> HexStr_:
        if self._encoded_request is not None:
            return self._encoded_request

        self._encoded_request = self._build(self.request, self._decoded_request)
        return self._encoded_request

    @property
    def encoded_response(self) -> HexStr_:
        if self._encoded_response is not None:
            return self._encoded_response

        response = self._build(self.response, self._decoded_response)
        if response and self.values:
            values = [
                self._build(self.values, v)
                for v in self._decoded_response.get(self.values_key, [])
            ]
            response = VALUE_SEPARATOR.join([response] + values)

        self._encoded_response = response
        return self._encoded_response

    @property
    def decoded_request(self) -> dict:
        if self._decoded_request is not None:
            return self._decoded_request

        self._decoded_request = self._parse(self.request, self._encoded_request)
        return self._decoded_request

    @property
    def decoded_response(self) -> dict:
        if self._decoded_response is not None:
            return self._decoded_response

        if self._encoded_response is None:
            return None

        combined = self._encoded_response.split(VALUE_SEPARATOR)
        errcode = self._parse(ErrorcodeEnum, combined[0])

        if int(errcode) < 0:
            self._decoded_response = CommandException(
                f'{self.name} failed with code {errcode}')
        else:
            response = self._parse(self.response, combined[0])
            if self.values:
                response[self.values_key] = [
                    self._parse(self.values, v)
                    for v in combined[1:]
                ]
            self._decoded_response = response

        return self._decoded_response

    def _build(self, struct: Struct, decoded: dict) -> HexStr_:
        if decoded is None:
            return None
        built_val = struct.build(decoded)
        return hexlify(built_val).decode()

    def _parse(self, struct: Struct, encoded: HexStr_) -> dict:
        """
        Parses struct, and returns a serializable Python object.
        """
        if encoded is None:
            return None

        def normalize(val):
            """
            Recursively converts construct Container values to serializable Python objects.
            Private items (key starts with '_') are filtered.
            """
            if isinstance(val, Container):
                return {
                    k: normalize(v)
                    for k, v in dict(val).items()
                    if not k.startswith('_')
                }
            else:
                return val

        return normalize(struct.parse(unhexlify(encoded)))


# Reoccurring data types - can be used as a macro
_PROFILE_LIST = Struct(PROFILE_LIST_KEY / ProfileListAdapter())
_OBJECT_ID = Struct(OBJECT_ID_KEY / Int16ub)
_SYSTEM_ID = Struct(SYSTEM_ID_KEY / Int16ub)
_OBJECT_TYPE = Struct(OBJECT_TYPE_KEY / Int16ub)
_OBJECT_DATA = Struct(OBJECT_DATA_KEY / GreedyBytes)
_OBJECT = _OBJECT_ID + _PROFILE_LIST + _OBJECT_TYPE + _OBJECT_DATA
_SYSTEM_OBJECT = _SYSTEM_ID + _OBJECT_TYPE + _OBJECT_DATA

# Special cases
_CREATE_ID = Struct(OBJECT_ID_KEY / Default(Int16ub, 0))  # 0 == assigned by controller


class ReadObjectCommand(Command):
    _OPCODE = OpcodeEnum.READ_OBJECT
    _REQUEST = _OBJECT_ID
    _RESPONSE = _OBJECT
    _VALUES = None


class WriteObjectCommand(Command):
    _OPCODE = OpcodeEnum.WRITE_OBJECT
    _REQUEST = _OBJECT
    _RESPONSE = _OBJECT
    _VALUES = None


class CreateObjectCommand(Command):
    _OPCODE = OpcodeEnum.CREATE_OBJECT
    _REQUEST = _CREATE_ID + _PROFILE_LIST + _OBJECT_TYPE + _OBJECT_DATA
    _RESPONSE = _OBJECT
    _VALUES = None


class DeleteObjectCommand(Command):
    _OPCODE = OpcodeEnum.DELETE_OBJECT
    _REQUEST = _OBJECT_ID
    _RESPONSE = None
    _VALUES = None


class ReadSystemObjectCommand(Command):
    _OPCODE = OpcodeEnum.READ_SYSTEM_OBJECT
    _REQUEST = _SYSTEM_ID + _OBJECT_TYPE
    _RESPONSE = _SYSTEM_OBJECT
    _VALUES = None


class WriteSystemObjectCommand(Command):
    _OPCODE = OpcodeEnum.WRITE_SYSTEM_OBJECT
    _REQUEST = _SYSTEM_OBJECT
    _RESPONSE = _SYSTEM_OBJECT
    _VALUES = None


class ReadActiveProfilesCommand(Command):
    _OPCODE = OpcodeEnum.READ_ACTIVE_PROFILES
    _REQUEST = None
    _RESPONSE = _PROFILE_LIST
    _VALUES = None


class WriteActiveProfilesCommand(Command):
    _OPCODE = OpcodeEnum.WRITE_ACTIVE_PROFILES
    _REQUEST = _PROFILE_LIST
    _RESPONSE = _PROFILE_LIST
    _VALUES = None


class ListActiveObjectsCommand(Command):
    _OPCODE = OpcodeEnum.LIST_ACTIVE_OBJECTS
    _REQUEST = None
    _RESPONSE = _PROFILE_LIST
    _VALUES = (OBJECT_LIST_KEY, _OBJECT)


class ListSavedObjectsCommand(Command):
    _OPCODE = OpcodeEnum.LIST_SAVED_OBJECTS
    _REQUEST = None
    _RESPONSE = _PROFILE_LIST
    _VALUES = (OBJECT_LIST_KEY, _OBJECT)


class ListSystemObjectsCommand(Command):
    _OPCODE = OpcodeEnum.LIST_SYSTEM_OBJECTS
    _REQUEST = None
    _RESPONSE = None
    _VALUES = (OBJECT_LIST_KEY, _SYSTEM_OBJECT)


class ClearProfileCommand(Command):
    _OPCODE = OpcodeEnum.CLEAR_PROFILE
    _REQUEST = _PROFILE_LIST
    _RESPONSE = None
    _VALUES = None


class FactoryResetCommand(Command):
    _OPCODE = OpcodeEnum.FACTORY_RESET
    _REQUEST = None
    _RESPONSE = None
    _VALUES = None


class RestartCommand(Command):
    _OPCODE = OpcodeEnum.RESTART
    _REQUEST = None
    _RESPONSE = None
    _VALUES = None
