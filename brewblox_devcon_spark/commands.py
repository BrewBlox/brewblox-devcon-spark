"""
Definitions for all commands that can be sent to the Spark.

The Command base class offers the functionality to convert dicts to and from byte strings,
based on the defined construct Struct.

Each child class of Command defines how the syntax for itself looks like.
"""

from abc import ABC
from binascii import hexlify, unhexlify

from brewblox_service import brewblox_logger
from construct import (Byte, Const, Container, Default, Enum, FlagsEnum,
                       GreedyBytes, GreedyRange, Int8sb, Int8ub, Int16ub,
                       ListContainer, Optional, Padding, Sequence, Struct,
                       Terminated)

LOGGER = brewblox_logger(__name__)

HexStr_ = str


VALUE_SEPARATOR = ','


OBJECT_ID_KEY = 'object_id'
SYSTEM_ID_KEY = 'system_object_id'
OBJECT_TYPE_KEY = 'object_type'
OBJECT_DATA_KEY = 'object_data'
OBJECT_LIST_KEY = 'objects'

PROFILE_ID_KEY = 'profile_id'
PROFILE_LIST_KEY = 'profiles'

FLAGS_KEY = 'flags'


OpcodeEnum = Enum(Byte,
                  READ_VALUE=1,  # read a value
                  WRITE_VALUE=2,  # write a value
                  CREATE_OBJECT=3,  # add object in a container
                  DELETE_OBJECT=4,  # delete the object at the specified location
                  LIST_OBJECTS=5,  # list objects in a container
                  FREE_SLOT=6,  # retrieves the next free slot in a container
                  CREATE_PROFILE=7,  # create a new profile
                  DELETE_PROFILE=8,  # delete a profile
                  ACTIVATE_PROFILE=9,  # activate a profile
                  LOG_VALUES=10,  # log values from the selected container
                  RESET=11,  # reset the device
                  FREE_SLOT_ROOT=12,  # find the next free slot in the root container
                  UNUSED=13,  # unused
                  LIST_PROFILES=14,  # list the define profile IDs and the active profile
                  READ_SYSTEM_VALUE=15,  # read the value of a system object
                  WRITE_SYSTEM_VALUE=16,  # write the value of a system object
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
        return hexlify(struct.build(decoded)).decode()

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
            if isinstance(val, ListContainer):
                return [normalize(v) for v in val]
            elif isinstance(val, Container):
                return {
                    k: normalize(v)
                    for k, v in dict(val).items()
                    if not k.startswith('_')
                }
            else:
                return val

        return normalize(struct.parse(unhexlify(encoded)))


# Reoccurring data types - can be used as a macro
_OBJECT_ID = Struct(OBJECT_ID_KEY / Int8ub)
_SYSTEM_ID = Struct(SYSTEM_ID_KEY / Int8ub)
_OBJECT_TYPE = Struct(OBJECT_TYPE_KEY / Int16ub)
_OBJECT_DATA = Struct(OBJECT_DATA_KEY / GreedyBytes)

_PROFILE_DATA = Int8sb
_PROFILE_ID = Struct(PROFILE_ID_KEY / _PROFILE_DATA)


class ReadValueCommand(Command):
    _OPCODE = OpcodeEnum.READ_VALUE
    _REQUEST = _OBJECT_ID + _OBJECT_TYPE
    _RESPONSE = _OBJECT_ID + _OBJECT_TYPE + _OBJECT_DATA
    _VALUES = None


class WriteValueCommand(Command):
    _OPCODE = OpcodeEnum.WRITE_VALUE
    _REQUEST = _OBJECT_ID + _OBJECT_TYPE + _OBJECT_DATA
    _RESPONSE = _OBJECT_ID + _OBJECT_TYPE + _OBJECT_DATA
    _VALUES = None


class CreateObjectCommand(Command):
    _OPCODE = OpcodeEnum.CREATE_OBJECT
    _REQUEST = _OBJECT_TYPE + _OBJECT_DATA
    _RESPONSE = _OBJECT_ID
    _VALUES = None


class DeleteObjectCommand(Command):
    _OPCODE = OpcodeEnum.DELETE_OBJECT
    _REQUEST = _OBJECT_ID
    _RESPONSE = None
    _VALUES = None


class ListObjectsCommand(Command):
    _OPCODE = OpcodeEnum.LIST_OBJECTS
    _REQUEST = _PROFILE_ID
    _RESPONSE = Struct(
        OBJECT_LIST_KEY / Optional(Sequence(_OBJECT_ID + _OBJECT_TYPE + _OBJECT_DATA)),
        Terminated
    )
    _VALUES = None


class FreeSlotCommand(Command):
    _OPCODE = OpcodeEnum.FREE_SLOT
    _REQUEST = _OBJECT_ID
    _RESPONSE = None
    _VALUES = None


class CreateProfileCommand(Command):
    _OPCODE = OpcodeEnum.CREATE_PROFILE
    _REQUEST = None
    _RESPONSE = _PROFILE_ID
    _VALUES = None


class DeleteProfileCommand(Command):
    _OPCODE = OpcodeEnum.DELETE_PROFILE
    _REQUEST = _PROFILE_ID
    _RESPONSE = None
    _VALUES = None


class ActivateProfileCommand(Command):
    _OPCODE = OpcodeEnum.ACTIVATE_PROFILE
    _REQUEST = _PROFILE_ID
    _RESPONSE = None
    _VALUES = None


class LogValuesCommand(Command):
    _OPCODE = OpcodeEnum.LOG_VALUES

    _REQUEST = Struct(
        FLAGS_KEY / FlagsEnum(Byte,
                              id_chain=1,
                              system_container=2,
                              default=0)
    ) + Optional(_OBJECT_ID)

    _RESPONSE = Struct(
        OBJECT_LIST_KEY / Optional(Sequence(Padding(1) + _OBJECT_ID + _OBJECT_TYPE + _OBJECT_DATA)),
        Terminated
    )
    _VALUES = None


class ResetCommand(Command):
    _OPCODE = OpcodeEnum.RESET
    _REQUEST = Struct(
        FLAGS_KEY / FlagsEnum(Byte,
                              erase_eeprom=1,
                              hard_reset=2,
                              default=0)
    )
    _RESPONSE = None
    _VALUES = None


class FreeSlotRootCommand(Command):
    _OPCODE = OpcodeEnum.FREE_SLOT_ROOT
    _REQUEST = _SYSTEM_ID
    _RESPONSE = None
    _VALUES = None


class ListProfilesCommand(Command):
    _OPCODE = OpcodeEnum.LIST_PROFILES
    _REQUEST = None
    _RESPONSE = _PROFILE_ID + Struct(
        PROFILE_LIST_KEY / GreedyRange(_PROFILE_DATA)
    )
    _VALUES = None


class ReadSystemValueCommand(Command):
    _OPCODE = OpcodeEnum.READ_SYSTEM_VALUE
    _REQUEST = _SYSTEM_ID + _OBJECT_TYPE
    _RESPONSE = _SYSTEM_ID + _OBJECT_TYPE + _OBJECT_DATA
    _VALUES = None


class WriteSystemValueCommand(Command):
    _OPCODE = OpcodeEnum.WRITE_SYSTEM_VALUE
    _REQUEST = _SYSTEM_ID + _OBJECT_TYPE + _OBJECT_DATA
    _RESPONSE = _SYSTEM_ID + _OBJECT_TYPE + _OBJECT_DATA
    _VALUES = None
