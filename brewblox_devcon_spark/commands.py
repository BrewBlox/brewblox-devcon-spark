"""
Definitions for all commands that can be sent to the Spark.

The Command base class offers the functionality to convert dicts to and from byte strings,
based on the defined construct Struct.

Each child class of Command defines how the syntax for itself looks like.
"""

from abc import ABC
from binascii import hexlify

from brewblox_service import brewblox_logger
from construct import (Adapter, Byte, Const, Enum, FlagsEnum, GreedyBytes,
                       Int8sb, Optional, Padding, RepeatUntil, Sequence,
                       Struct, Terminated)

LOGGER = brewblox_logger(__name__)


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


class VariableLengthIDAdapter(Adapter):
    """Adapter for the brewblox ID schema

    Individual IDs are 7 bit, with the first bit reserved for a nesting flag.
    Range is 0-127 / 0x0-0x7F

    If the first bit is set, it indicates that the current byte is a container ID,
    and more IDs are to follow.
    Example:
        bytes: [1000 0011] [0000 0111]

    Here a container with ID 3 contains an object with ID 7
    """

    def __init__(self):
        # Predicate: repeat until ID does not contain a nesting flag
        super().__init__(RepeatUntil(lambda obj, lst, ctx: obj & 0x80 == 0x00, Byte))

    def _encode(self, obj, context, path):
        # Add a nesting flag to all but the last object
        return [b | 0x80 for b in obj[:-1]] + [obj[-1]]

    def _decode(self, obj, context, path):
        # Remove all nesting flags
        # No need to worry about whether it's the last ID
        return [b & 0x7F for b in obj]


class CommandException(Exception):
    pass


class Command(ABC):
    """
    Base class for all commands.
    This class handles encoding and decoding of arguments.

    Subclasses are expected to set static class variables to define their protocol.
    The constructor will fail if these are not defined.

    Required class variables:
        _OPCODE
        _REQUEST
        _RESPONSE

    Opcode must always be set, request and response can be None.

    Request or response being None does not mean the controller will literally send nothing.
    Opcode/error code are always sent, and will be part of the decoded request/response.
    """

    def __init__(self):
        opcode = self.__class__._OPCODE
        self._opcode = Struct('opcode' / Const(OpcodeEnum.encmapping[opcode], Byte))

        request = self.__class__._REQUEST or Struct()
        self._request = self.opcode + request

        self._status = Struct('errcode' / ErrorcodeEnum)
        response = self.__class__._RESPONSE or Struct()
        self._response = self.status + response

        # Initialize empty
        self._set_data()

    def __str__(self):
        return f'<{type(self).__name__} [{self.name}]>'

    def _set_data(self,
                  encoded: tuple=(None, None),
                  decoded: tuple=(None, None)):
        self._encoded_request: bytes = encoded[0]
        self._encoded_response: bytes = encoded[1]

        self._decoded_request: dict = decoded[0]
        self._decoded_response: dict = decoded[1]

    def _pretty_raw(self, raw: bytes) -> str:
        return hexlify(raw) if raw is not None else None

    def from_args(self, **kwargs):
        self._set_data(decoded=(kwargs, None))
        LOGGER.debug(f'{self} from args: {kwargs}')
        return self

    def from_encoded(self, request: bytes=None, response: bytes=None):
        self._set_data(encoded=(request, response))
        LOGGER.debug(f'{self} from encoded: {self._pretty_raw(request)} | {self._pretty_raw(response)}')
        return self

    def from_decoded(self, request: dict=None, response: dict=None):
        self._set_data(decoded=(request, response))
        LOGGER.debug(f'{self} from decoded: {request} | {response}')
        return self

    @property
    def name(self):
        return self.__class__._OPCODE

    @property
    def opcode(self):
        return self._opcode

    @property
    def request(self):
        return self._request

    @property
    def status(self):
        return self._status

    @property
    def response(self):
        return self._response

    @property
    def encoded_request(self):
        if self._should_convert(self._encoded_request, self._decoded_request):
            self._encoded_request = self.request.build(self._decoded_request)

        return self._encoded_request

    @property
    def encoded_response(self):
        if self._should_convert(self._encoded_response, self._decoded_response):
            self._encoded_response = self.response.build(self._decoded_response)

        return self._encoded_response

    @property
    def decoded_request(self):
        if self._should_convert(self._decoded_request, self._encoded_request):
            self._decoded_request = self._parse(self.request, self._encoded_request)

        return self._decoded_request

    @property
    def decoded_response(self):
        if self._should_convert(self._decoded_response, self._encoded_response):
            self._decoded_response = \
                self._parse_error() or \
                self._parse(self.response, self._encoded_response)

        return self._decoded_response

    def _parse(self, struct: Struct, encoded: bytes) -> dict:
        """
        Parses struct, and returns a dict.
        Internal construct items (key starts with '_') are filtered.
        """
        return {
            k: v
            for k, v in dict(struct.parse(encoded)).items()
            if not k.startswith('_')
        }

    def _should_convert(self, dest, src) -> bool:
        return dest is None and src is not None

    def _parse_error(self):
        status = self.status.parse(self._encoded_response).errcode

        if int(status) < 0:
            return CommandException(f'{self.name} failed with code {status}')
        else:
            return None


# Reoccurring data types - can be used as a macro
_OBJECT_ID = Struct(OBJECT_ID_KEY / VariableLengthIDAdapter())
_SYSTEM_ID = Struct(SYSTEM_ID_KEY / VariableLengthIDAdapter())
_OBJECT_TYPE = Struct(OBJECT_TYPE_KEY / Byte)
_OBJECT_DATA = Struct(OBJECT_DATA_KEY / GreedyBytes)

_PROFILE_ID = Struct(PROFILE_ID_KEY / Int8sb)


class ReadValueCommand(Command):
    _OPCODE = OpcodeEnum.READ_VALUE
    _REQUEST = _OBJECT_ID + _OBJECT_TYPE
    _RESPONSE = _OBJECT_ID + _OBJECT_TYPE + _OBJECT_DATA


class WriteValueCommand(Command):
    _OPCODE = OpcodeEnum.WRITE_VALUE
    _REQUEST = _OBJECT_ID + _OBJECT_TYPE + _OBJECT_DATA
    _RESPONSE = _OBJECT_ID + _OBJECT_TYPE + _OBJECT_DATA


class CreateObjectCommand(Command):
    _OPCODE = OpcodeEnum.CREATE_OBJECT
    _REQUEST = _OBJECT_TYPE + _OBJECT_DATA
    _RESPONSE = _OBJECT_ID


class DeleteObjectCommand(Command):
    _OPCODE = OpcodeEnum.DELETE_OBJECT
    _REQUEST = _OBJECT_ID
    _RESPONSE = None


class ListObjectsCommand(Command):
    _OPCODE = OpcodeEnum.LIST_OBJECTS
    _REQUEST = _PROFILE_ID
    _RESPONSE = Struct(
        OBJECT_LIST_KEY / Optional(Sequence(_OBJECT_ID + _OBJECT_TYPE + _OBJECT_DATA)),
        Terminated
    )


class FreeSlotCommand(Command):
    _OPCODE = OpcodeEnum.FREE_SLOT
    _REQUEST = _OBJECT_ID
    _RESPONSE = None


class CreateProfileCommand(Command):
    _OPCODE = OpcodeEnum.CREATE_PROFILE
    _REQUEST = None
    _RESPONSE = _PROFILE_ID


class DeleteProfileCommand(Command):
    _OPCODE = OpcodeEnum.DELETE_PROFILE
    _REQUEST = _PROFILE_ID
    _RESPONSE = None


class ActivateProfileCommand(Command):
    _OPCODE = OpcodeEnum.ACTIVATE_PROFILE
    _REQUEST = _PROFILE_ID
    _RESPONSE = None


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


class ResetCommand(Command):
    _OPCODE = OpcodeEnum.RESET
    _REQUEST = Struct(
        FLAGS_KEY / FlagsEnum(Byte,
                              erase_eeprom=1,
                              hard_reset=2,
                              default=0)
    )
    _RESPONSE = None


class FreeSlotRootCommand(Command):
    _OPCODE = OpcodeEnum.FREE_SLOT_ROOT
    _REQUEST = _SYSTEM_ID
    _RESPONSE = None


class ListProfilesCommand(Command):
    _OPCODE = OpcodeEnum.LIST_PROFILES
    _REQUEST = None
    _RESPONSE = _PROFILE_ID + Struct(
        PROFILE_LIST_KEY / Sequence(_PROFILE_ID)
    )


class ReadSystemValueCommand(Command):
    _OPCODE = OpcodeEnum.READ_SYSTEM_VALUE
    _REQUEST = _SYSTEM_ID + _OBJECT_TYPE
    _RESPONSE = _SYSTEM_ID + _OBJECT_TYPE + _OBJECT_DATA


class WriteSystemValueCommand(Command):
    _OPCODE = OpcodeEnum.WRITE_SYSTEM_VALUE
    _REQUEST = _SYSTEM_ID + _OBJECT_TYPE + _OBJECT_DATA
    _RESPONSE = _SYSTEM_ID + _OBJECT_TYPE + _OBJECT_DATA
