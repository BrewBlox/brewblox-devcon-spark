from construct import (Adapter, Byte, Const, Enum, FlagsEnum, Int8sb, Int8ub,
                       Optional, Padding, RepeatUntil, Sequence, Struct,
                       Terminated)

COMMAND_DEFS = dict()


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
                     STREAM_ERROR=-1,
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


class CommandDefinition():
    def __init__(self,
                 opcode=None,
                 request=Struct(),
                 response=Struct()):
        self.opcode = opcode

        self.opcode_struct = Struct('opcode' / Const(OpcodeEnum.encmapping[self.opcode], Byte))
        self.request = self.opcode_struct + request

        self.status = Struct('errcode' / ErrorcodeEnum)
        self.response = self.status + response


class CommandException(Exception):
    pass


class RequestConverter():
    def __init__(self, command_name: str, data: dict):
        self._definition = COMMAND_DEFS[command_name.upper()]
        self._data = data

    @property
    def raw_request(self):
        return self._definition.request.build(self._data)


class ResponseConverter():
    def __init__(self, raw_request: str, raw_response: str):
        assert raw_request is not None, 'Raw request not specified'
        assert raw_response is not None, 'Raw response not specified'

        self._definition = self._identify(raw_request)
        self._raw_request = raw_request
        self._raw_response = raw_response

    def _identify(self, raw_request: bytes) -> CommandDefinition:
        try:
            opcode = OpcodeEnum.parse(raw_request)
            return COMMAND_DEFS[opcode]
        except KeyError as ex:
            # Add some relevant info
            raise KeyError(f'Failed to identify command for opcode [{opcode}]')

    def _is_ok(self):
        return self._raw_response[0] >= 0

    @property
    def raw_request(self):
        return self._raw_request

    @property
    def error(self):
        if self._is_ok():
            return None

        status = self._definition.status.parse(self._raw_response)
        return CommandException(f'{self._definition.opcode} failed with status {status}')

    @property
    def response(self):
        if not self._is_ok():
            return None

        return self._definition.response.parse(self._raw_response)


# Generics
OBJECT_ID = Struct('id' / VariableLengthIDAdapter())
OBJECT_TYPE = Struct('type' / Byte)
OBJECT_SIZE = Struct('size' / Byte)
OBJECT_DATA = Struct('data' / Byte[:])

PROFILE_ID = Struct('profile_id' / Int8sb)


def _define_command(opcode, request=Struct(), response=Struct()):
    COMMAND_DEFS[opcode] = CommandDefinition(opcode, request, response)


_define_command(
    opcode=OpcodeEnum.READ_VALUE,
    request=OBJECT_ID + OBJECT_TYPE + OBJECT_SIZE,
    response=OBJECT_TYPE + OBJECT_SIZE + OBJECT_DATA,
)

_define_command(
    opcode=OpcodeEnum.WRITE_VALUE,
    request=OBJECT_ID + OBJECT_TYPE + OBJECT_SIZE + OBJECT_DATA,
    response=OBJECT_TYPE + OBJECT_SIZE + OBJECT_DATA
)

_define_command(
    opcode=OpcodeEnum.CREATE_OBJECT,
    request=OBJECT_TYPE + OBJECT_SIZE + OBJECT_DATA
)

_define_command(
    opcode=OpcodeEnum.DELETE_OBJECT,
    request=OBJECT_ID
)

_define_command(
    opcode=OpcodeEnum.LIST_OBJECTS,
    request=PROFILE_ID,
    response=Struct(
        Padding(1),  # FIXME Protocol error?
        'objects' / Optional(Sequence(OBJECT_ID + OBJECT_TYPE + OBJECT_SIZE + OBJECT_DATA)),
        'terminator' / Const(0x00, Byte),
        Terminated
    )
)

_define_command(
    opcode=OpcodeEnum.FREE_SLOT,
    request=OBJECT_ID
)

_define_command(
    opcode=OpcodeEnum.CREATE_PROFILE,
    response=PROFILE_ID
)

_define_command(
    opcode=OpcodeEnum.DELETE_PROFILE,
    request=PROFILE_ID
)

_define_command(
    opcode=OpcodeEnum.ACTIVATE_PROFILE,
    request=PROFILE_ID
)

_define_command(
    opcode=OpcodeEnum.LOG_VALUES,
    request=Struct(
        'flags' / FlagsEnum(Byte,
                            id_chain=1,
                            system_container=2,
                            default=0)
    ) + Optional(OBJECT_ID),
    response=Struct(
        'objects' / Optional(Sequence(Padding(1) + OBJECT_ID + OBJECT_TYPE + OBJECT_SIZE + OBJECT_DATA)),
        'terminator' / Const(0x00, Byte),
        Terminated
    )
)

_define_command(
    opcode=OpcodeEnum.RESET,
    request=Struct(
        'flags' / FlagsEnum(Byte,
                            erase_eeprom=1,
                            hard_reset=2,
                            default=0)
    )
)

_define_command(
    opcode=OpcodeEnum.FREE_SLOT_ROOT,
    request=OBJECT_ID
)

_define_command(
    opcode=OpcodeEnum.LIST_PROFILES,
    response=PROFILE_ID + Struct(
        'defined_profiles' / Sequence(Int8ub)
    )
)

_define_command(
    opcode=OpcodeEnum.READ_SYSTEM_VALUE,
    request=OBJECT_ID + OBJECT_TYPE + OBJECT_SIZE,
    response=OBJECT_TYPE + OBJECT_SIZE + OBJECT_DATA,
)

_define_command(
    opcode=OpcodeEnum.WRITE_SYSTEM_VALUE,
    request=OBJECT_ID + OBJECT_TYPE + OBJECT_SIZE + OBJECT_DATA,
    response=OBJECT_TYPE + OBJECT_SIZE + OBJECT_DATA
)
