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
                       GreedyBytes, Int8ul, Int16ul, Struct)

from brewblox_devcon_spark import exceptions

LOGGER = brewblox_logger(__name__)

HexStr_ = str


VALUE_SEPARATOR = ','

OBJECT_ID_KEY = 'object_id'
OBJECT_TYPE_KEY = 'object_type'
OBJECT_DATA_KEY = 'object_data'
OBJECT_LIST_KEY = 'objects'
PROFILE_LIST_KEY = 'profiles'


OpcodeEnum = Enum(Int8ul,
                  NONE=0,
                  READ_OBJECT=1,
                  WRITE_OBJECT=2,
                  CREATE_OBJECT=3,
                  DELETE_OBJECT=4,
                  LIST_OBJECTS=5,
                  READ_STORED_OBJECT=6,
                  LIST_STORED_OBJECTS=7,
                  CLEAR_OBJECTS=8,
                  REBOOT=9,
                  FACTORY_RESET=10,
                  )

ErrorcodeEnum = Enum(Int8ul,
                     OK=0,
                     UNKNOWN_ERROR=1,

                     # object creation
                     INSUFFICIENT_HEAP=4,

                     # generic stream errors
                     STREAM_ERROR_UNSPECIFIED=8,
                     OUTPUT_STREAM_WRITE_ERROR=9,
                     INPUT_STREAM_READ_ERROR=10,
                     INPUT_STREAM_DECODING_ERROR=11,
                     OUTPUT_STREAM_ENCODING_ERROR=12,

                     # storage errors
                     INSUFFICIENT_PERSISTENT_STORAGE=16,
                     PERSISTED_OBJECT_NOT_FOUND=17,
                     INVALID_PERSISTED_BLOCK_TYPE=18,
                     COULD_NOT_READ_PERSISTED_BLOCK_SIZE=19,
                     PERSISTED_BLOCK_STREAM_ERROR=20,
                     PERSISTED_STORAGE_WRITE_ERROR=21,
                     CRC_ERROR_IN_STORED_OBJECT=22,

                     # invalid actions
                     OBJECT_NOT_WRITABLE=32,
                     OBJECT_NOT_READABLE=33,
                     OBJECT_NOT_CREATABLE=34,
                     OBJECT_NOT_DELETABLE=35,

                     # invalid parameters
                     INVALID_COMMAND=63,
                     INVALID_OBJECT_ID=64,
                     INVALID_OBJECT_TYPE=65,
                     INVALID_OBJECT_PROFILES=66,
                     CRC_ERROR_IN_COMMAND=67,
                     OBJECT_DATA_NOT_ACCEPTED=68,

                     # freak events that should not be possible
                     WRITE_TO_INACTIVE_OBJECT=200,
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


class CRC8():
    CRC_TABLE = (0x00, 0x5e, 0xbc, 0xe2, 0x61, 0x3f, 0xdd, 0x83,
                 0xc2, 0x9c, 0x7e, 0x20, 0xa3, 0xfd, 0x1f, 0x41,
                 0x9d, 0xc3, 0x21, 0x7f, 0xfc, 0xa2, 0x40, 0x1e,
                 0x5f, 0x01, 0xe3, 0xbd, 0x3e, 0x60, 0x82, 0xdc,
                 0x23, 0x7d, 0x9f, 0xc1, 0x42, 0x1c, 0xfe, 0xa0,
                 0xe1, 0xbf, 0x5d, 0x03, 0x80, 0xde, 0x3c, 0x62,
                 0xbe, 0xe0, 0x02, 0x5c, 0xdf, 0x81, 0x63, 0x3d,
                 0x7c, 0x22, 0xc0, 0x9e, 0x1d, 0x43, 0xa1, 0xff,
                 0x46, 0x18, 0xfa, 0xa4, 0x27, 0x79, 0x9b, 0xc5,
                 0x84, 0xda, 0x38, 0x66, 0xe5, 0xbb, 0x59, 0x07,
                 0xdb, 0x85, 0x67, 0x39, 0xba, 0xe4, 0x06, 0x58,
                 0x19, 0x47, 0xa5, 0xfb, 0x78, 0x26, 0xc4, 0x9a,
                 0x65, 0x3b, 0xd9, 0x87, 0x04, 0x5a, 0xb8, 0xe6,
                 0xa7, 0xf9, 0x1b, 0x45, 0xc6, 0x98, 0x7a, 0x24,
                 0xf8, 0xa6, 0x44, 0x1a, 0x99, 0xc7, 0x25, 0x7b,
                 0x3a, 0x64, 0x86, 0xd8, 0x5b, 0x05, 0xe7, 0xb9,
                 0x8c, 0xd2, 0x30, 0x6e, 0xed, 0xb3, 0x51, 0x0f,
                 0x4e, 0x10, 0xf2, 0xac, 0x2f, 0x71, 0x93, 0xcd,
                 0x11, 0x4f, 0xad, 0xf3, 0x70, 0x2e, 0xcc, 0x92,
                 0xd3, 0x8d, 0x6f, 0x31, 0xb2, 0xec, 0x0e, 0x50,
                 0xaf, 0xf1, 0x13, 0x4d, 0xce, 0x90, 0x72, 0x2c,
                 0x6d, 0x33, 0xd1, 0x8f, 0x0c, 0x52, 0xb0, 0xee,
                 0x32, 0x6c, 0x8e, 0xd0, 0x53, 0x0d, 0xef, 0xb1,
                 0xf0, 0xae, 0x4c, 0x12, 0x91, 0xcf, 0x2d, 0x73,
                 0xca, 0x94, 0x76, 0x28, 0xab, 0xf5, 0x17, 0x49,
                 0x08, 0x56, 0xb4, 0xea, 0x69, 0x37, 0xd5, 0x8b,
                 0x57, 0x09, 0xeb, 0xb5, 0x36, 0x68, 0x8a, 0xd4,
                 0x95, 0xcb, 0x29, 0x77, 0xf4, 0xaa, 0x48, 0x16,
                 0xe9, 0xb7, 0x55, 0x0b, 0x88, 0xd6, 0x34, 0x6a,
                 0x2b, 0x75, 0x97, 0xc9, 0x4a, 0x14, 0xf6, 0xa8,
                 0x74, 0x2a, 0xc8, 0x96, 0x15, 0x4b, 0xa9, 0xf7,
                 0xb6, 0xe8, 0x0a, 0x54, 0xd7, 0x89, 0x6b, 0x35)

    @classmethod
    def calculate(cls, msg):
        current = 0
        for c in msg:
            current = cls._crc_byte(current, c)
        return bytes([current])

    @classmethod
    def _crc_byte(cls, old_crc, byte):
        res = cls.CRC_TABLE[old_crc & 0xFF ^ byte & 0xFF]
        return res


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
        errcode = self._parse(ErrorcodeEnum, combined[0], False)

        try:
            if int(errcode) != 0:
                raise exceptions.CommandException(f'{self.name} failed with code {errcode}')

            response = self._parse(self.response, combined[0])
            if self.values:
                response[self.values_key] = [
                    self._parse(self.values, v)
                    for v in combined[1:]
                ]
            self._decoded_response = response

        except exceptions.CommandException as ex:
            self._decoded_response = ex

        return self._decoded_response

    def _build(self, struct: Struct, decoded: dict) -> HexStr_:
        if decoded is None:
            return None
        built_val = struct.build(decoded)
        built_val += CRC8.calculate(built_val)
        return hexlify(built_val).decode()

    def _parse(self, struct: Struct, encoded: HexStr_, crc=True) -> dict:
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

        byte_val = unhexlify(encoded)

        if crc:
            if CRC8.calculate(byte_val) == b'\x00':
                byte_val = byte_val[:-1]
            else:
                raise exceptions.CRCFailed(f'{self} failed CRC check')

        return normalize(struct.parse(byte_val))


# Reoccurring data types - can be used as a macro
_PROFILE_LIST = Struct(PROFILE_LIST_KEY / ProfileListAdapter())
_OBJECT_ID = Struct(OBJECT_ID_KEY / Int16ul)
_OBJECT_TYPE = Struct(OBJECT_TYPE_KEY / Int16ul)
_OBJECT_DATA = Struct(OBJECT_DATA_KEY / GreedyBytes)
_OBJECT = _OBJECT_ID + _PROFILE_LIST + _OBJECT_TYPE + _OBJECT_DATA

# Special cases
_CREATE_ID = Struct(OBJECT_ID_KEY / Default(Int16ul, 0))  # 0 == assigned by controller


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


class ListObjectsCommand(Command):
    _OPCODE = OpcodeEnum.LIST_OBJECTS
    _REQUEST = None
    _RESPONSE = None
    _VALUES = (OBJECT_LIST_KEY, _OBJECT)


class ReadStoredObjectCommand(Command):
    _OPCODE = OpcodeEnum.READ_STORED_OBJECT
    _REQUEST = _OBJECT_ID
    _RESPONSE = _OBJECT
    _VALUES = None


class ListStoredObjectsCommand(Command):
    _OPCODE = OpcodeEnum.LIST_STORED_OBJECTS
    _REQUEST = None
    _RESPONSE = None
    _VALUES = (OBJECT_LIST_KEY, _OBJECT)


class ClearObjectsCommand(Command):
    _OPCODE = OpcodeEnum.CLEAR_OBJECTS
    _REQUEST = None
    _RESPONSE = None
    _VALUES = None


class FactoryResetCommand(Command):
    _OPCODE = OpcodeEnum.FACTORY_RESET
    _REQUEST = None
    _RESPONSE = None
    _VALUES = None


class RebootCommand(Command):
    _OPCODE = OpcodeEnum.REBOOT
    _REQUEST = None
    _RESPONSE = None
    _VALUES = None
