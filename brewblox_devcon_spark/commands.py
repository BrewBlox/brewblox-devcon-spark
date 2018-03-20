from construct import (Adapter, Byte, Const, Default, Enum, FlagsEnum, Int8sb,
                       Int8ub, Optional, Padding, PascalString, PrefixedArray,
                       RepeatUntil, Sequence, Struct, Terminated, VarInt)

COMMANDS = dict()


CBoxOpcodeEnum = Enum(Byte,
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
                      SET_SYSTEM_VALUE=16,  # write the value of a system object
                      SET_MASK_VALUE=17
                      )


# FIXME: Move to codec library
BrewBloxObjectTypeEnum = Enum(Byte,
                              TEMPERATURE_SENSOR=6,
                              SETPOINT_SIMPLE=7
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


class Command():
    def __init__(self,
                 opcode=None,
                 header=Struct(),
                 request=Struct(),
                 response=Struct()):
        self.opcode = opcode
        self.opcode_struct = Struct('opcode' / Const(CBoxOpcodeEnum.encmapping[self.opcode], Byte))
        self.header = self.opcode_struct + header
        self.request = self.header + request
        self.response = self.header + response


def _add_command(opcode, header=Struct(), request=Struct(), response=Struct()):
    COMMANDS[opcode] = Command(opcode, header, request, response)


def identify(unhexed: bytes) -> 'Command':
    opcode = CBoxOpcodeEnum.parse(unhexed)
    command = COMMANDS[opcode]
    return command


_add_command(
    opcode=CBoxOpcodeEnum.CREATE_OBJECT,
    header=Struct(
        'id' / VariableLengthIDAdapter()
    ),
    request=Struct(
        'type' / BrewBloxObjectTypeEnum,
        'reserved_size' / Byte,
        'data' / PrefixedArray(VarInt, Byte)
    ),
    response=Struct(
        'type' / Optional(BrewBloxObjectTypeEnum),
        'reserved_size' / Byte,
        'data' / Optional(PrefixedArray(VarInt, Byte)),
        'status' / Int8sb,
        Terminated
    )
)

_add_command(
    opcode=CBoxOpcodeEnum.CREATE_PROFILE,
    response=Struct(
        'profile_id' / Int8sb,
        Terminated
    )
)

_add_command(
    opcode=CBoxOpcodeEnum.ACTIVATE_PROFILE,
    header=Struct(
        'profile_id' / Int8sb
    ),
    response=Struct(
        'status' / Int8sb,
        Terminated
    )
)

_add_command(
    opcode=CBoxOpcodeEnum.LIST_PROFILES,
    response=Struct(
        'active_profile' / Int8ub
        #    'defined_profiles' / Sequence(Int8ub)
    )
)

_add_command(
    opcode=CBoxOpcodeEnum.LIST_OBJECTS,
    header=Struct(
        'profile_id' / Int8sb
    ),
    response=Struct(
        'status' / Int8sb,
        Padding(1),  # FIXME Protocol error?
        'objects' / Optional(Sequence(COMMANDS['CREATE_OBJECT'].request)),
        'terminator' / Const(0x00, Byte),
        Terminated
    )
)

_add_command(
    opcode=CBoxOpcodeEnum.READ_VALUE,
    header=Struct(
        'id' / VariableLengthIDAdapter(),
        'type' / BrewBloxObjectTypeEnum
    ),
    request=Struct(
        'size' / Default(Int8ub, 0)
    ),
    response=Struct(
        'expectedsize' / Int8sb,
        'real-type' / BrewBloxObjectTypeEnum,
        Padding(1),
        'data' / Optional(PascalString(VarInt, 'utf8')),  # TODO(Bob): should encoding be utf8?
        Terminated
    )
)

_add_command(
    opcode=CBoxOpcodeEnum.DELETE_OBJECT,
    header=Struct(
        'id' / VariableLengthIDAdapter()
    ),
    response=Struct(
        'status' / Int8sb,
        Terminated
    )
)

_add_command(
    opcode=CBoxOpcodeEnum.RESET,
    request=Struct(
        'flags' / FlagsEnum(Byte,
                            erase_eeprom=1,
                            hard_reset=2,
                            default=0)
    )
)
